from . import __version__ as _version

app_name = "webshop"
app_title = "Webshop"
app_publisher = "Frappe Technologies Pvt. Ltd."
app_description = "Open Source eCommerce Platform"
app_email = "contact@frappe.io"
app_license = "GNU General Public License (v3)"
app_version = _version

required_apps = ["payments", "erpnext"]

# Desktop icon
add_to_apps_screen = [
	{
		"name": "webshop",
		"title": "Webshop",
		"icon": "shopping-cart",
		"route": "/app/webshop",
	}
]

web_include_css = "webshop-web.bundle.css"

web_include_js = [
	"web.bundle.js",
	"/assets/webshop/js/indonesia_logistics.js"
]

after_install = "webshop.setup.install.after_install"
on_logout = "webshop.webshop.shopping_cart.utils.clear_cart_count"
on_session_creation = [
    "webshop.webshop.utils.portal.update_debtors_account",
    "webshop.webshop.shopping_cart.utils.set_cart_count",
]
update_website_context = [
    "webshop.webshop.shopping_cart.utils.update_website_context",
]

website_generators = ["Website Item", "Item Group"]

override_doctype_class = {
    "Payment Request": "webshop.webshop.doctype.override_doctype.payment_request.PaymentRequest",
    "Item Group": "webshop.webshop.doctype.override_doctype.item_group.WebshopItemGroup",
    "Item": "webshop.webshop.doctype.override_doctype.item.WebshopItem",
}

doctype_js = {
    "Item": "public/js/override/item.js",
    "Homepage": "public/js/override/homepage.js",
}

doc_events = {
    "Item": {
        "on_update": [
            "webshop.webshop.crud_events.item.update_website_item.execute",
            "webshop.webshop.crud_events.item.invalidate_item_variants_cache.execute",
        ],
        "before_rename": [
            "webshop.webshop.crud_events.item.validate_duplicate_website_item.execute",
        ],
        "after_rename": [
            "webshop.webshop.crud_events.item.invalidate_item_variants_cache.execute",
        ],
    },
    "Sales Taxes and Charges Template": {
        "on_update": [
            "webshop.webshop.doctype.webshop_settings.webshop_settings.validate_cart_settings",
        ],
    },
    "Quotation": {
        "validate": [
            "webshop.webshop.crud_events.quotation.validate_shopping_cart_items.execute",
        ],
        "on_update": [
            "webshop.abandonment.tracker.track_cart_activity",
        ],
        "on_submit": [
            "webshop.abandonment.tracker.mark_cart_recovered",
        ],
    },
    "Sales Order": {
        "before_save": [
            "webshop.webshop.crud_events.sales_order.process_metadata.process_order_metadata"
        ],
        "on_submit": [
            "webshop.abandonment.tracker.mark_cart_recovered_from_order",
            "webshop.integrations.whatsapp_notifications.send_order_confirmation",
        ],
    },
    "Delivery Note": {
        "on_submit": [
            "webshop.integrations.whatsapp_notifications.send_order_shipped",
        ],
    },
    "Payment Entry": {
        "on_submit": [
            "webshop.integrations.whatsapp_notifications.send_payment_received",
        ],
    },
    "Price List": {
        "validate": [
            "webshop.webshop.crud_events.price_list.check_impact_on_cart.execute"
        ],
    },
    "Tax Rule": {
        "validate": [
            "webshop.webshop.crud_events.tax_rule.validate_use_for_cart.execute",
        ],
    },
}

# Scheduled Tasks
scheduler_events = {
    "hourly": [
        "webshop.abandonment.scheduler.detect_abandoned_carts",
        "webshop.abandonment.scheduler.send_abandonment_notifications",
        "webshop.abandonment.scheduler.sync_cart_status",
    ],
    "daily": [
        "webshop.abandonment.scheduler.cleanup_expired_carts",
    ],
}

has_website_permission = {
    "Website Item": "webshop.webshop.doctype.website_item.website_item.has_website_permission_for_website_item",
    "Item Group": "webshop.webshop.doctype.website_item.website_item.has_website_permission_for_item_group"
}
