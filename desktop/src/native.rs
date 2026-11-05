use anyhow::{Result, bail};
use base64::{Engine, engine::general_purpose::STANDARD};
use serde_json::{Value, json};

pub fn system_info() -> Value {
    let mut system = sysinfo::System::new();
    system.refresh_memory();
    system.refresh_cpu_all();
    let rendering = if cfg!(feature = "desktop-web") {
        "Tauri / Windows WebView2"
    } else if cfg!(feature = "legacy-egui") {
        "Rust egui / wgpu Direct3D 12"
    } else {
        "Native services / headless CLI"
    };
    json!({"os":sysinfo::System::long_os_version(),"host":sysinfo::System::host_name(),"cpu":system.cpus().first().map(|c| c.brand()),"logical_cores":system.cpus().len(),"memory_total_bytes":system.total_memory(),"memory_used_bytes":system.used_memory(),"rendering":rendering,"inference":"Deep partner server / configured model provider"})
}

#[cfg(windows)]
pub fn screenshot() -> Result<Value> {
    use windows_sys::Win32::{Graphics::Gdi::*, UI::WindowsAndMessaging::*};
    // The DC and bitmap stay on one CPU worker and are always released there.
    unsafe {
        let x = GetSystemMetrics(SM_XVIRTUALSCREEN);
        let y = GetSystemMetrics(SM_YVIRTUALSCREEN);
        let width = GetSystemMetrics(SM_CXVIRTUALSCREEN);
        let height = GetSystemMetrics(SM_CYVIRTUALSCREEN);
        if width <= 0 || height <= 0 || (width as i64 * height as i64) > 100_000_000 {
            bail!("屏幕尺寸无效");
        }
        let screen = GetDC(std::ptr::null_mut());
        if screen.is_null() {
            bail!("无法读取桌面");
        }
        let memory = CreateCompatibleDC(screen);
        let bitmap = CreateCompatibleBitmap(screen, width, height);
        if memory.is_null() || bitmap.is_null() {
            if !memory.is_null() {
                DeleteDC(memory);
            }
            if !bitmap.is_null() {
                DeleteObject(bitmap);
            }
            ReleaseDC(std::ptr::null_mut(), screen);
            bail!("无法创建截图缓冲区");
        }
        let old = SelectObject(memory, bitmap);
        let result = (|| -> Result<Value> {
            if BitBlt(
                memory,
                0,
                0,
                width,
                height,
                screen,
                x,
                y,
                SRCCOPY | CAPTUREBLT,
            ) == 0
            {
                bail!("桌面复制失败");
            }
            SelectObject(memory, old);
            let mut info = BITMAPINFO::default();
            info.bmiHeader = BITMAPINFOHEADER {
                biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: width,
                biHeight: -height,
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB,
                ..Default::default()
            };
            let mut pixels = vec![0u8; width as usize * height as usize * 4];
            if GetDIBits(
                screen,
                bitmap,
                0,
                height as u32,
                pixels.as_mut_ptr().cast(),
                &mut info,
                DIB_RGB_COLORS,
            ) == 0
            {
                bail!("截图像素读取失败");
            }
            for p in pixels.chunks_exact_mut(4) {
                p.swap(0, 2);
                p[3] = 255;
            }
            let image = image::RgbaImage::from_raw(width as u32, height as u32, pixels)
                .ok_or_else(|| anyhow::anyhow!("截图尺寸不匹配"))?;
            let image = image::DynamicImage::ImageRgba8(image).resize(
                1920,
                1200,
                image::imageops::FilterType::Triangle,
            );
            let mut png = std::io::Cursor::new(Vec::new());
            image.write_to(&mut png, image::ImageFormat::Png)?;
            Ok(
                json!({"data":STANDARD.encode(png.into_inner()),"mimeType":"image/png","screen_origin":{"x":x,"y":y},"screen_width":width,"screen_height":height,"image_width":image.width(),"image_height":image.height(),"note":"desktop_click 使用原始屏幕像素坐标；截图可能经过等比例缩小"}),
            )
        })();
        SelectObject(memory, old);
        DeleteObject(bitmap);
        DeleteDC(memory);
        ReleaseDC(std::ptr::null_mut(), screen);
        result
    }
}

#[cfg(windows)]
pub fn desktop_click(x: i32, y: i32, right: bool) -> Result<Value> {
    use windows_sys::Win32::UI::{Input::KeyboardAndMouse::*, WindowsAndMessaging::*};
    unsafe {
        let left = GetSystemMetrics(SM_XVIRTUALSCREEN);
        let top = GetSystemMetrics(SM_YVIRTUALSCREEN);
        let w = GetSystemMetrics(SM_CXVIRTUALSCREEN);
        let h = GetSystemMetrics(SM_CYVIRTUALSCREEN);
        if x < left || y < top || x >= left + w || y >= top + h {
            bail!("坐标不在桌面范围内");
        }
        if SetCursorPos(x, y) == 0 {
            bail!("鼠标定位失败");
        }
        let flags = if right {
            [MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP]
        } else {
            [MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP]
        };
        let inputs = flags.map(|dw_flags| INPUT {
            r#type: INPUT_MOUSE,
            Anonymous: INPUT_0 {
                mi: MOUSEINPUT {
                    dwFlags: dw_flags,
                    ..Default::default()
                },
            },
        });
        send(&inputs)?;
    }
    Ok(json!({"clicked":true,"x":x,"y":y}))
}

#[cfg(windows)]
pub fn desktop_type(text: &str) -> Result<Value> {
    use windows_sys::Win32::UI::Input::KeyboardAndMouse::*;
    if text.len() > 16000 {
        bail!("单次桌面输入上限 16000 字节");
    }
    let inputs: Vec<INPUT> = text
        .encode_utf16()
        .flat_map(|code| {
            [KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP].map(|dw_flags| INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wScan: code,
                        dwFlags: dw_flags,
                        ..Default::default()
                    },
                },
            })
        })
        .collect();
    send(&inputs)?;
    Ok(json!({"typed":true}))
}

#[cfg(windows)]
pub fn desktop_key(key: &str) -> Result<Value> {
    use windows_sys::Win32::UI::Input::KeyboardAndMouse::*;
    let keys: Result<Vec<u16>> = key
        .to_uppercase()
        .split('+')
        .map(|part| {
            Ok(match part.trim() {
                "CTRL" | "CONTROL" => VK_CONTROL,
                "ALT" => VK_MENU,
                "SHIFT" => VK_SHIFT,
                "WIN" => VK_LWIN,
                "ENTER" => VK_RETURN,
                "TAB" => VK_TAB,
                "ESC" | "ESCAPE" => VK_ESCAPE,
                "SPACE" => VK_SPACE,
                "BACKSPACE" => VK_BACK,
                "DELETE" => VK_DELETE,
                "UP" => VK_UP,
                "DOWN" => VK_DOWN,
                "LEFT" => VK_LEFT,
                "RIGHT" => VK_RIGHT,
                "HOME" => VK_HOME,
                "END" => VK_END,
                "PAGEUP" => VK_PRIOR,
                "PAGEDOWN" => VK_NEXT,
                p if p.len() == 1 && p.as_bytes()[0].is_ascii_alphanumeric() => {
                    p.as_bytes()[0] as u16
                }
                _ => bail!("不支持的按键 {part}"),
            })
        })
        .collect();
    let keys = keys?;
    if keys.is_empty() || keys.len() > 4 {
        bail!("组合键需要 1–4 个按键");
    }
    let mut inputs = Vec::new();
    for k in &keys {
        inputs.push(INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: *k,
                    ..Default::default()
                },
            },
        });
    }
    for k in keys.iter().rev() {
        inputs.push(INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: *k,
                    dwFlags: KEYEVENTF_KEYUP,
                    ..Default::default()
                },
            },
        });
    }
    send(&inputs)?;
    Ok(json!({"pressed":key}))
}

#[cfg(windows)]
fn send(inputs: &[windows_sys::Win32::UI::Input::KeyboardAndMouse::INPUT]) -> Result<()> {
    use windows_sys::Win32::UI::Input::KeyboardAndMouse::*;
    if inputs.is_empty() {
        return Ok(());
    }
    let sent = unsafe {
        SendInput(
            inputs.len() as u32,
            inputs.as_ptr(),
            std::mem::size_of::<INPUT>() as i32,
        )
    };
    if sent != inputs.len() as u32 {
        bail!("系统未接受全部输入；目标窗口可能以管理员权限运行");
    }
    Ok(())
}

#[cfg(not(windows))]
pub fn screenshot() -> Result<Value> {
    bail!("当前版本的桌面截图仅支持 Windows")
}
#[cfg(not(windows))]
pub fn desktop_click(_: i32, _: i32, _: bool) -> Result<Value> {
    bail!("仅支持 Windows")
}
#[cfg(not(windows))]
pub fn desktop_type(_: &str) -> Result<Value> {
    bail!("仅支持 Windows")
}
#[cfg(not(windows))]
pub fn desktop_key(_: &str) -> Result<Value> {
    bail!("仅支持 Windows")
}
