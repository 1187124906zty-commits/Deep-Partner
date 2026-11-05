fn main() {
    println!("cargo:rerun-if-changed=ui-dist");
    #[cfg(feature = "desktop-web")]
    {
        tauri_build::build();
    }
    #[cfg(not(feature = "desktop-web"))]
    native_resource();
}
#[cfg(not(feature = "desktop-web"))]
fn native_resource() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=icons/icon.ico");
    #[cfg(windows)]
    {
        let mut resource = winresource::WindowsResource::new();
        resource
            .set_icon("icons/icon.ico")
            .set("ProductName", "Deep partner")
            .set("FileDescription", "Deep partner Native Desktop");
        resource.compile().expect("Windows resources");
    }
}
