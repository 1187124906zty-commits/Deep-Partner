//! Windows protects the optional revocable device credential for the signed-in user.
use anyhow::{Result, bail};
use std::path::Path;

#[cfg(windows)]
fn protect(input: &[u8], encrypt: bool) -> Result<Vec<u8>> {
    use windows_sys::Win32::{Foundation::LocalFree, Security::Cryptography::*};
    let blob = CRYPT_INTEGER_BLOB {
        cbData: input.len() as u32,
        pbData: input.as_ptr() as *mut u8,
    };
    let mut output = CRYPT_INTEGER_BLOB::default();
    let ok = unsafe {
        if encrypt {
            CryptProtectData(
                &blob,
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null_mut(),
                std::ptr::null(),
                CRYPTPROTECT_UI_FORBIDDEN,
                &mut output,
            )
        } else {
            CryptUnprotectData(
                &blob,
                std::ptr::null_mut(),
                std::ptr::null(),
                std::ptr::null_mut(),
                std::ptr::null(),
                CRYPTPROTECT_UI_FORBIDDEN,
                &mut output,
            )
        }
    };
    if ok == 0 {
        bail!("Windows 无法解锁此设备凭证");
    }
    let bytes =
        unsafe { std::slice::from_raw_parts(output.pbData, output.cbData as usize).to_vec() };
    unsafe {
        LocalFree(output.pbData.cast());
    }
    Ok(bytes)
}
#[cfg(not(windows))]
fn protect(_: &[u8], _: bool) -> Result<Vec<u8>> {
    bail!("设备凭证保存需要 Windows")
}
pub fn save(path: &Path, value: &str) -> Result<()> {
    std::fs::write(path, protect(value.as_bytes(), true)?)?;
    Ok(())
}
pub fn load(path: &Path) -> Result<String> {
    Ok(String::from_utf8(protect(&std::fs::read(path)?, false)?)?)
}

#[cfg(test)]
mod tests {
    #[test]
    #[cfg(windows)]
    fn roundtrip_is_encrypted() {
        let input = b"test-revocable-device-credential";
        let output = super::protect(input, true).unwrap();
        assert_ne!(output, input);
        assert_eq!(super::protect(&output, false).unwrap(), input);
    }
}
