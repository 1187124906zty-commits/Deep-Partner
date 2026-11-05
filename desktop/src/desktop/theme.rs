use egui::{Color32, FontId, Pos2, Rect, Sense, Stroke, Ui, Vec2};

#[derive(Clone, Copy)]
pub struct Palette {
    pub bg: Color32,
    pub fg: Color32,
    pub card: Color32,
    pub rail: Color32,
    pub muted: Color32,
    pub border: Color32,
    pub hover: Color32,
    pub selected: Color32,
    pub accent: Color32,
    pub on_accent: Color32,
}
const fn rgb(hex: u32) -> Color32 {
    Color32::from_rgb((hex >> 16) as u8, (hex >> 8) as u8, hex as u8)
}
pub const DARK: Palette = Palette {
    bg: rgb(0x1a1918),
    fg: rgb(0xe8e4de),
    card: rgb(0x242220),
    rail: rgb(0x2a2725),
    muted: rgb(0x9b9590),
    border: rgb(0x3a3634),
    hover: rgb(0x302d2a),
    selected: rgb(0x242220),
    accent: rgb(0xd4734b),
    on_accent: rgb(0x1a1918),
};
pub const CREAM: Palette = Palette {
    bg: rgb(0xfdfcf9),
    fg: rgb(0x1c1816),
    card: Color32::WHITE,
    rail: rgb(0xf5f2ea),
    muted: rgb(0x6d645a),
    border: rgb(0xe6decc),
    hover: rgb(0xece7d8),
    selected: rgb(0xece7d8),
    accent: rgb(0xb0501e),
    on_accent: Color32::WHITE,
};
pub const SNOW: Palette = Palette {
    bg: Color32::WHITE,
    fg: rgb(0x0d0d0d),
    card: Color32::WHITE,
    rail: rgb(0xf7f7f7),
    muted: rgb(0x6e6e6e),
    border: rgb(0xe5e5e5),
    hover: rgb(0xf2f2f2),
    selected: rgb(0xececec),
    accent: rgb(0x2563eb),
    on_accent: Color32::WHITE,
};
pub const KRILL_DARK: Palette = Palette {
    bg: Color32::BLACK,
    fg: rgb(0xededed),
    card: rgb(0x0a0a0a),
    rail: rgb(0x111111),
    muted: rgb(0xa1a1aa),
    border: rgb(0x242424),
    hover: rgb(0x191919),
    selected: rgb(0x242424),
    accent: rgb(0x10a37f),
    on_accent: Color32::WHITE,
};
pub const KRILL_LIGHT: Palette = Palette {
    bg: rgb(0xf6f6f7),
    fg: rgb(0x18181b),
    card: Color32::WHITE,
    rail: rgb(0xf4f4f5),
    muted: rgb(0x71717a),
    border: rgb(0xe4e4e7),
    hover: rgb(0xf4f4f5),
    selected: Color32::WHITE,
    accent: rgb(0x10a37f),
    on_accent: Color32::WHITE,
};
pub fn palette(id: &str) -> Palette {
    match id {
        "cream" => CREAM,
        "snow" => SNOW,
        _ => DARK,
    }
}
pub fn apply(ctx: &egui::Context, id: &str, login: bool) {
    let dark = id == "dark";
    let p = if login {
        if dark { KRILL_DARK } else { KRILL_LIGHT }
    } else {
        palette(id)
    };
    let theme = if dark {
        egui::Theme::Dark
    } else {
        egui::Theme::Light
    };
    let mut s = (*ctx.style_of(theme)).clone();
    s.visuals = if dark {
        egui::Visuals::dark()
    } else {
        egui::Visuals::light()
    };
    s.visuals.override_text_color = Some(p.fg);
    s.visuals.panel_fill = p.bg;
    s.visuals.window_fill = p.card;
    s.visuals.extreme_bg_color = p.bg;
    s.visuals.faint_bg_color = p.rail;
    s.visuals.selection.bg_fill = p.selected;
    s.visuals.selection.stroke = Stroke::new(1., p.fg);
    s.visuals.hyperlink_color = p.accent;
    for widget in [
        &mut s.visuals.widgets.noninteractive,
        &mut s.visuals.widgets.inactive,
    ] {
        widget.bg_fill = p.card;
        widget.weak_bg_fill = Color32::TRANSPARENT;
        widget.bg_stroke = Stroke::new(1., p.border);
        widget.fg_stroke = Stroke::new(1., p.fg);
        widget.corner_radius = egui::CornerRadius::same(8);
    }
    s.visuals.widgets.hovered.bg_fill = p.hover;
    s.visuals.widgets.hovered.weak_bg_fill = p.hover;
    s.visuals.widgets.hovered.bg_stroke = Stroke::new(1., p.border);
    s.visuals.widgets.hovered.fg_stroke = Stroke::new(1., p.fg);
    s.visuals.widgets.hovered.corner_radius = egui::CornerRadius::same(8);
    s.visuals.widgets.active.bg_fill = p.selected;
    s.visuals.widgets.active.weak_bg_fill = p.selected;
    s.visuals.widgets.active.bg_stroke = Stroke::new(1., p.accent);
    s.visuals.widgets.active.fg_stroke = Stroke::new(1., p.fg);
    s.visuals.widgets.active.corner_radius = egui::CornerRadius::same(8);
    s.spacing.item_spacing = Vec2::new(8., 8.);
    s.spacing.button_padding = Vec2::new(10., 7.);
    s.spacing.interact_size.y = 32.;
    s.spacing.scroll.bar_width = 5.;
    s.animation_time = 0.10;
    s.text_styles
        .insert(egui::TextStyle::Body, FontId::proportional(14.));
    s.text_styles
        .insert(egui::TextStyle::Button, FontId::proportional(13.));
    s.text_styles
        .insert(egui::TextStyle::Small, FontId::proportional(12.));
    s.text_styles
        .insert(egui::TextStyle::Heading, FontId::proportional(28.));
    ctx.set_theme(theme);
    ctx.set_style_of(theme, s);
}
pub fn current(ui: &Ui) -> Palette {
    let v = ui.visuals();
    let dark = v.dark_mode;
    if v.panel_fill == KRILL_DARK.bg {
        KRILL_DARK
    } else if v.panel_fill == KRILL_LIGHT.bg {
        KRILL_LIGHT
    } else if dark {
        DARK
    } else if v.panel_fill == CREAM.bg {
        CREAM
    } else {
        SNOW
    }
}
#[derive(Clone, Copy)]
pub enum Icon {
    Home,
    Book,
    Folder,
    Partners,
    Sliders,
    Chat,
    Search,
    Panel,
    Plus,
    Edit,
    Calendar,
    Board,
    Settings,
    User,
    Computer,
    Brain,
    Code,
    Paperclip,
    Arrow,
    Stop,
    Sun,
    Moon,
    Eye,
    Check,
    File,
    Grid,
    More,
}
pub fn icon(ui: &Ui, center: Pos2, icon: Icon, size: f32, color: Color32) {
    let p = ui.painter();
    let stroke = Stroke::new(1.35, color);
    let unit = size / 24.;
    let xy = |x: f32, y: f32| Pos2::new(center.x + (x - 12.) * unit, center.y + (y - 12.) * unit);
    let line = |points: &[(f32, f32)]| {
        p.add(egui::Shape::line(
            points.iter().map(|(x, y)| xy(*x, *y)).collect(),
            stroke,
        ))
    };
    let rect = |a: (f32, f32), b: (f32, f32)| {
        p.rect_stroke(
            Rect::from_two_pos(xy(a.0, a.1), xy(b.0, b.1)),
            2.,
            stroke,
            egui::StrokeKind::Inside,
        )
    };
    match icon {
        Icon::Home => {
            line(&[
                (3., 10.),
                (12., 3.),
                (21., 10.),
                (21., 21.),
                (3., 21.),
                (3., 10.),
            ]);
            line(&[(9., 21.), (9., 14.), (15., 14.), (15., 21.)]);
        }
        Icon::Book => {
            line(&[
                (12., 5.),
                (7., 3.),
                (3., 4.),
                (3., 20.),
                (7., 19.),
                (12., 21.),
                (17., 19.),
                (21., 20.),
                (21., 4.),
                (17., 3.),
                (12., 5.),
                (12., 21.),
            ]);
        }
        Icon::Folder => {
            line(&[
                (3., 7.),
                (3., 4.),
                (9., 4.),
                (12., 7.),
                (21., 7.),
                (21., 20.),
                (3., 20.),
                (3., 7.),
                (21., 7.),
            ]);
        }
        Icon::Partners => {
            p.circle_stroke(xy(8., 8.), 4. * unit, stroke);
            p.circle_stroke(xy(18., 9.), 3. * unit, stroke);
            line(&[
                (1., 21.),
                (2., 16.),
                (5., 14.),
                (11., 14.),
                (14., 17.),
                (14., 21.),
            ]);
            line(&[(16., 15.), (20., 15.), (23., 19.), (23., 21.)]);
        }
        Icon::Sliders => {
            for (y, x) in [(5., 8.), (12., 16.), (19., 10.)] {
                line(&[(3., y), (x - 2., y)]);
                line(&[(x + 2., y), (21., y)]);
                p.circle_stroke(xy(x, y), 2. * unit, stroke);
            }
        }
        Icon::Chat => {
            p.rect_stroke(
                Rect::from_two_pos(xy(3., 3.), xy(21., 18.)),
                5. * unit,
                stroke,
                egui::StrokeKind::Inside,
            );
            line(&[(4., 17.), (3., 22.), (9., 18.)]);
        }
        Icon::Search => {
            p.circle_stroke(xy(10., 10.), 6.5 * unit, stroke);
            line(&[(15., 15.), (21., 21.)]);
        }
        Icon::Panel => {
            rect((3., 3.), (21., 21.));
            line(&[(9., 3.), (9., 21.)]);
        }
        Icon::Plus => {
            line(&[(5., 12.), (19., 12.)]);
            line(&[(12., 5.), (12., 19.)]);
        }
        Icon::Edit => {
            line(&[
                (4., 16.),
                (15., 5.),
                (19., 9.),
                (8., 20.),
                (3., 21.),
                (4., 16.),
            ]);
            line(&[(15., 5.), (18., 2.), (22., 6.), (19., 9.)]);
        }
        Icon::Calendar => {
            rect((3., 5.), (21., 21.));
            line(&[(3., 10.), (21., 10.)]);
            line(&[(8., 2.), (8., 7.)]);
            line(&[(16., 2.), (16., 7.)]);
        }
        Icon::Board => {
            rect((3., 3.), (21., 21.));
            for x in [9., 15.] {
                line(&[(x, 3.), (x, 21.)]);
            }
        }
        Icon::Settings => {
            p.circle_stroke(center, 7. * unit, stroke);
            p.circle_stroke(center, 2.5 * unit, stroke);
            for a in 0..8 {
                let a = a as f32 * std::f32::consts::PI / 4.;
                line(&[
                    (12. + 7. * a.cos(), 12. + 7. * a.sin()),
                    (12. + 10. * a.cos(), 12. + 10. * a.sin()),
                ]);
            }
        }
        Icon::User => {
            p.circle_stroke(xy(12., 7.), 4. * unit, stroke);
            line(&[
                (4., 22.),
                (5., 16.),
                (9., 13.),
                (15., 13.),
                (19., 16.),
                (20., 22.),
            ]);
        }
        Icon::Computer => {
            rect((2., 3.), (22., 17.));
            line(&[(12., 17.), (12., 22.)]);
            line(&[(7., 22.), (17., 22.)]);
        }
        Icon::Brain => {
            p.circle_stroke(xy(8., 7.), 4. * unit, stroke);
            p.circle_stroke(xy(16., 7.), 4. * unit, stroke);
            p.circle_stroke(xy(6., 14.), 4. * unit, stroke);
            p.circle_stroke(xy(18., 14.), 4. * unit, stroke);
            line(&[(7., 18.), (9., 22.), (12., 20.), (15., 22.), (18., 18.)]);
            line(&[(12., 4.), (12., 20.)]);
        }
        Icon::Code => {
            line(&[(8., 5.), (2., 12.), (8., 19.)]);
            line(&[(16., 5.), (22., 12.), (16., 19.)]);
        }
        Icon::Paperclip => {
            line(&[
                (7., 13.),
                (15., 5.),
                (19., 5.),
                (21., 9.),
                (10., 21.),
                (5., 21.),
                (2., 17.),
                (3., 13.),
                (14., 2.),
            ]);
        }
        Icon::Arrow => {
            line(&[(12., 21.), (12., 4.)]);
            line(&[(5., 11.), (12., 4.), (19., 11.)]);
        }
        Icon::Stop => {
            p.rect_filled(Rect::from_two_pos(xy(6., 6.), xy(18., 18.)), 2., color);
        }
        Icon::Sun => {
            p.circle_stroke(center, 4. * unit, stroke);
            for a in 0..8 {
                let a = a as f32 * std::f32::consts::PI / 4.;
                line(&[
                    (12. + 7. * a.cos(), 12. + 7. * a.sin()),
                    (12. + 10. * a.cos(), 12. + 10. * a.sin()),
                ]);
            }
        }
        Icon::Moon => {
            line(&[
                (18., 3.),
                (11., 3.),
                (5., 8.),
                (4., 14.),
                (8., 20.),
                (15., 21.),
                (21., 16.),
                (14., 16.),
                (10., 11.),
                (11., 6.),
                (18., 3.),
            ]);
        }
        Icon::Eye => {
            line(&[
                (1., 12.),
                (6., 6.),
                (12., 4.),
                (18., 6.),
                (23., 12.),
                (18., 18.),
                (12., 20.),
                (6., 18.),
                (1., 12.),
            ]);
            p.circle_stroke(center, 3. * unit, stroke);
        }
        Icon::Check => {
            line(&[(4., 12.), (10., 18.), (21., 5.)]);
        }
        Icon::File => {
            line(&[
                (5., 2.),
                (15., 2.),
                (21., 8.),
                (21., 22.),
                (5., 22.),
                (5., 2.),
            ]);
            line(&[(15., 2.), (15., 8.), (21., 8.)]);
        }
        Icon::Grid => {
            for (x, y) in [(3., 3.), (14., 3.), (3., 14.), (14., 14.)] {
                rect((x, y), (x + 7., y + 7.));
            }
        }
        Icon::More => {
            for x in [5., 12., 19.] {
                p.circle_filled(xy(x, 12.), 1.4 * unit, color);
            }
        }
    }
}
pub fn icon_button(
    ui: &mut Ui,
    id: impl std::hash::Hash + std::fmt::Debug,
    kind: Icon,
    tip: &str,
) -> egui::Response {
    let p = current(ui);
    let (rect, _) = ui.allocate_exact_size(Vec2::splat(30.), Sense::hover());
    #[cfg(test)]
    ui.ctx()
        .data_mut(|d| d.insert_temp(egui::Id::unique(("icon-rect", tip)), rect));
    let response = ui
        .interact(rect, ui.scope_id().with(id), Sense::click())
        .on_hover_text(tip);
    response.widget_info(|| egui::WidgetInfo::labeled(egui::Role::Button, ui.is_enabled(), tip));
    if response.hovered() {
        ui.painter().rect_filled(rect, 6., p.hover);
    }
    icon(
        ui,
        rect.center(),
        kind,
        17.,
        if response.hovered() { p.fg } else { p.muted },
    );
    response
}
pub fn row(
    ui: &mut Ui,
    id: impl std::hash::Hash + std::fmt::Debug,
    kind: Icon,
    label: &str,
    selected: bool,
    width: f32,
) -> egui::Response {
    let p = current(ui);
    let (rect, _) = ui.allocate_exact_size(Vec2::new(width, 34.), Sense::hover());
    let response = ui.interact(rect, ui.scope_id().with(id), Sense::click());
    response.widget_info(|| egui::WidgetInfo::labeled(egui::Role::Button, ui.is_enabled(), label));
    let hover =
        ui.ctx()
            .animate_bool_with_time(response.id.with("hover"), response.hovered(), 0.12);
    if selected || hover > 0. {
        let fill = if selected {
            p.selected
        } else {
            Color32::from(
                egui::Rgba::from(p.rail) * (1. - hover) + egui::Rgba::from(p.hover) * hover,
            )
        };
        ui.painter().rect_filled(rect, 7., fill);
    }
    icon(
        ui,
        Pos2::new(rect.left() + 18., rect.center().y),
        kind,
        17.,
        if selected { p.fg } else { p.muted },
    );
    let galley = ui
        .painter()
        .layout_no_wrap(label.to_string(), FontId::proportional(13.), p.fg);
    let clip = rect.shrink2(Vec2::new(7., 0.));
    ui.painter().with_clip_rect(clip).galley(
        Pos2::new(rect.left() + 36., rect.center().y - galley.size().y / 2.),
        galley,
        p.fg,
    );
    response
}
pub fn brand(ui: &mut Ui, size: f32, _color: Color32) {
    ui.add(
        egui::Image::new(egui::include_image!("../../assets/brand-mark.svg"))
            .fit_to_exact_size(Vec2::splat(size)),
    );
}
pub fn wordmark(ui: &mut Ui, size: f32) {
    let p = current(ui);
    let first = ui.painter().layout_no_wrap(
        "Deep".into(),
        FontId::new(size, egui::FontFamily::Name("Lora".into())),
        p.fg,
    );
    let accent = if ui.visuals().dark_mode {
        Color32::from_rgb(213, 186, 145)
    } else {
        Color32::from_rgb(49, 113, 126)
    };
    let second = ui.painter().layout_no_wrap(
        "partner".into(),
        FontId::new(size, egui::FontFamily::Name("Lora Italic".into())),
        accent,
    );
    let gap = size * 0.23;
    let height = first.size().y.max(second.size().y);
    let (rect, _) = ui.allocate_exact_size(
        Vec2::new(first.size().x + gap + second.size().x, height),
        Sense::hover(),
    );
    let x = rect.left() + first.size().x + gap;
    ui.painter().galley(rect.left_top(), first, p.fg);
    ui.painter()
        .galley(Pos2::new(x, rect.top()), second, accent);
}
