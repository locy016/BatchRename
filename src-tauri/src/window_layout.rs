pub const MIN_WINDOW_WIDTH: u32 = 1180;
pub const MIN_WINDOW_HEIGHT: u32 = 760;

pub fn calculate_window_size(work_width: u32, work_height: u32) -> (u32, u32) {
    let work_width = work_width.max(1);
    let work_height = work_height.max(1);
    let ratio = work_width as f64 / work_height as f64;

    let (mut width, mut height) = if ratio < 1.15 {
        let width = ((work_width as f64 * 0.90).round() as u32).max(MIN_WINDOW_WIDTH);
        let height = ((work_height as f64 * 0.68).round() as u32)
            .min((width as f64 * 1.15).round() as u32)
            .max(MIN_WINDOW_HEIGHT);
        (width, height)
    } else if ratio > 2.0 {
        let height = ((work_height as f64 * 0.68).round() as u32).max(MIN_WINDOW_HEIGHT);
        let width = ((work_width as f64 * 0.46).round() as u32)
            .min((height as f64 * 1.70).round() as u32)
            .max(MIN_WINDOW_WIDTH);
        (width, height)
    } else {
        (
            ((work_width as f64 * 0.50).round() as u32).max(MIN_WINDOW_WIDTH),
            ((work_height as f64 * 0.50).round() as u32).max(MIN_WINDOW_HEIGHT),
        )
    };

    if work_width >= MIN_WINDOW_WIDTH {
        width = width.min(work_width);
    }
    if work_height >= MIN_WINDOW_HEIGHT {
        height = height.min(work_height);
    }
    (width, height)
}
