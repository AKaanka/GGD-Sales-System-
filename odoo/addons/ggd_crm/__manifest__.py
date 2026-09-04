{
    "name": "Germany Growth Desk CRM Controls",
    "summary": "Qualification, outreach approval, reply analysis, and AI audit fields for GGD",
    "version": "19.0.1.15.0",
    "category": "Sales/CRM",
    "author": "Germany Growth Desk",
    "license": "LGPL-3",
    "depends": ["crm"],
    "data": [
        "security/ggd_security.xml",
        "data/ggd_config_parameter.xml",
        "views/crm_lead_views.xml",
        "views/ggd_review_desk_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ggd_crm/static/src/dark_mode_systray.js",
            "ggd_crm/static/src/dark_mode_systray.xml",
        ],
        # Served only when the cookie asks for dark, so light mode pays
        # nothing for it.
        "web.assets_web_dark": [
            "ggd_crm/static/src/dark_theme.dark.scss",
        ],
    },
    "installable": True,
    "application": False,
}
