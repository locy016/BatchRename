use std::fs;

use batch_rename_lib::domain::models::OperationLogV1;

fn main() {
    let mut arguments = std::env::args_os().skip(1);
    let input = arguments.next().expect("需要输入路径");
    let output = arguments.next().expect("需要输出路径");
    let operation: OperationLogV1 = serde_json::from_slice(&fs::read(input).unwrap()).unwrap();
    fs::write(output, serde_json::to_vec_pretty(&operation).unwrap()).unwrap();
}
