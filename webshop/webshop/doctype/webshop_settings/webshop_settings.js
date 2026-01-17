// Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Webshop Settings", {
  onload: function (frm) {
    if (frm.doc.__onload && frm.doc.__onload.quotation_series) {
      frm.fields_dict.quotation_series.df.options =
        frm.doc.__onload.quotation_series;
      frm.refresh_field("quotation_series");
    }

    frm.set_query("payment_gateway_account", function () {
      return {
        filters: {
          payment_channel: ["in", ["Email", "Phone"]],
        },
      };
    });
  },
  refresh: function (frm) {
    if (frm.doc.enabled) {
      frm
        .get_field("store_page_docs")
        .$wrapper.removeClass("hide-control")
        .html(
          `<div>${__("Follow these steps to create a landing page for your store")}:
					<a href="https://docs.erpnext.com/docs/user/manual/en/website/store-landing-page"
						style="color: var(--gray-600)">
						docs/store-landing-page
					</a>
				</div>`,
        );
    }

    frappe.model.with_doctype("Website Item", () => {
      const web_item_meta = frappe.get_meta("Website Item");

      const valid_fields = web_item_meta.fields
        .filter(
          (df) =>
            ["Link", "Table MultiSelect"].includes(df.fieldtype) && !df.hidden,
        )
        .map((df) => ({ label: df.label, value: df.fieldname }));

      frm
        .get_field("filter_fields")
        .grid.update_docfield_property("fieldname", "options", valid_fields);
    });

    // Webshop Headless Integration Dashboard
    frappe.call({
      method:
        "webshop.webshop.doctype.webshop_settings.webshop_settings.get_active_integrations",
      callback: function (r) {
        if (r.message) {
          let integrations = r.message;
          let html = `
						<div class="form-message ${integrations.travel ? "green" : "yellow"}" style="margin-bottom: 10px;">
							<div class="d-flex" style="align-items: center;">
								<span class="indicator-pill ${integrations.travel ? "green" : "orange"} no-margin"></span>
								<strong style="margin-left: 8px;">Travel Integration:</strong> 
								<span style="margin-left: 5px;">${integrations.travel ? "Active (bizops_tour_travel)" : "Not Installed"}</span>
							</div>
						</div>
						<div class="form-message ${integrations.wallet ? "green" : "gray"}" style="margin-bottom: 10px;">
							<div class="d-flex" style="align-items: center;">
								<span class="indicator-pill ${integrations.wallet ? "green" : "gray"} no-margin"></span>
								<strong style="margin-left: 8px;">Wallet Integration:</strong> 
								<span style="margin-left: 5px;">${integrations.wallet ? "Active" : "Not Installed"}</span>
							</div>
						</div>
					`;

          // Inject into a HTML field placeholder if exists, or append to introduction
          if (frm.fields_dict["integration_dashboard"]) {
            frm.fields_dict["integration_dashboard"].$wrapper.html(html);
          } else {
            // Fallback: append to top
            $(html).insertBefore(frm.fields_dict["enabled"].$wrapper);
          }
        }
      },
    });
  },
  enabled: function (frm) {
    if (frm.doc.enabled === 1) {
      frm.set_value("enable_variants", 1);
    } else {
      frm.set_value("company", "");
      frm.set_value("price_list", "");
      frm.set_value("default_customer_group", "");
      frm.set_value("quotation_series", "");
    }
  },
});
