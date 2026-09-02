import { Channel, invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import type { MatchOptions, OperationLogV1, RenameCandidate } from '../types/contracts'

export interface PreviewSummary { matched:number; ready:number; unchanged:number; conflicts:number; invalid:number }
export interface ScanProgress { jobId:string; phase:string; scannedTotal:number; matchedTotal:number; warning?:string }
export interface PreviewPage { items:RenameCandidate[]; total:number; offset:number; limit:number; summary:PreviewSummary; warnings:string[] }
export interface OperationSummary { identifier:string; createdAt:string; updatedAt:string; root:string; search:string; replacement:string; status:string; itemCount:number; successCount:number; failedCount:number }
export interface OperationPage { items:OperationSummary[]; total:number }
export interface UndoCheck { operationId:string; token:string; safe:boolean; summary:string; items:Array<{itemIndex:number;currentSource:string;restoreTarget:string;kind:string;safe:boolean;detail:string}> }
export interface DesktopApi { chooseDirectory():Promise<string|null>; startScan(options:MatchOptions,onProgress:(event:ScanProgress)=>void):Promise<string>; cancelActiveJob():Promise<void>; buildPreview(jobId:string,replacement:string,renameExtension:boolean):Promise<PreviewPage>; getPreviewPage(jobId:string,offset:number,limit:number):Promise<PreviewPage>; execute(jobId:string,options:object,onProgress:(event:object)=>void):Promise<{operationId:string;succeeded:number;skipped:number;failed:number}>; queryOperations(query:object):Promise<OperationPage>; getOperation(identifier:string):Promise<OperationLogV1>; checkUndo(identifier:string):Promise<UndoCheck>; undo(identifier:string,token:string,onProgress:(event:object)=>void):Promise<{succeeded:number;failed:number}>; loadPreferences():Promise<{appearance:string}>; savePreferences(appearance:string):Promise<void> }

const inDesktop = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
function events<T>(handler:(event:T)=>void){const channel=new Channel<T>();channel.onmessage=handler;return channel}
function desktopOnly<T>(command:string,args?:Record<string,unknown>):Promise<T>{return inDesktop()?invoke<T>(command,args):Promise.reject(new Error('当前为浏览器预览环境'))}

export const desktopApi:DesktopApi={
  async chooseDirectory(){if(!inDesktop())return null;const value=await open({directory:true,multiple:false});return typeof value==='string'?value:null},
  startScan:(options,h)=>desktopOnly('start_scan',{options,events:events(h)}),
  cancelActiveJob:()=>desktopOnly('cancel_active_job'),
  buildPreview:(jobId,replacement,renameExtension)=>desktopOnly('build_rename_preview',{jobId,replacement,renameExtension}),
  getPreviewPage:(jobId,offset,limit)=>desktopOnly('get_preview_page',{jobId,offset,limit}),
  execute:(jobId,options,h)=>desktopOnly('execute_rename',{jobId,options,events:events(h)}),
  queryOperations:(query)=>inDesktop()?invoke('query_operations',{query}):Promise.resolve({items:[],total:0}),
  getOperation:(identifier)=>desktopOnly('get_operation',{identifier}),
  checkUndo:(identifier)=>desktopOnly('check_undo',{identifier}),
  undo:(identifier,token,h)=>desktopOnly('undo_operation',{identifier,token,events:events(h)}),
  loadPreferences:()=>inDesktop()?invoke('load_preferences'):Promise.resolve({appearance:'system'}),
  savePreferences:(appearance)=>inDesktop()?invoke('save_preferences',{appearance}):Promise.resolve(),
}
