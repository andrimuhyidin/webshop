frappe.provide("webshop.indonesia_logistics");

webshop.indonesia_logistics = {
	init: function() {
		if (window.location.pathname !== "/cart") return;
		this.bind_events();
	},

	bind_events: function() {
		const me = this;
		// Listen for address selection updates
		$(document).on('click', '.address-card', function() {
			const $card = $(this);
			const type = $card.closest('[data-address-type]').attr('data-address-type');
			if (type === 'shipping') {
				const address_name = $card.closest('[data-address-name]').attr('data-address-name');
				me.on_address_selected(address_name);
			}
		});

		// Also handle the "Set Address" button in the dialog
		$(document).ajaxComplete(function(event, xhr, settings) {
			if (settings.url.indexOf('update_cart_address') !== -1) {
				const shipping_address = $('[data-section="shipping-address"]')
					.find('[data-address-name][data-active]').attr('data-address-name');
				if (shipping_address) {
					me.on_address_selected(shipping_address);
				}
			}
		});
	},

	on_address_selected: function(address_name) {
		const me = this;
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Address",
				name: address_name
			},
			callback: function(r) {
				if (r.message && r.message.country === "Indonesia") {
					me.fetch_rates(r.message);
				} else {
					me.clear_logistics_ui();
				}
			}
		});
	},

	fetch_rates: function(address_doc) {
		const me = this;
		const city_id = address_doc.custom_rajaongkir_city_id || address_doc.city; // Fallback or mapping needed
		
		if (!city_id) {
			console.warn("Indonesia Shipping: City ID missing in Address");
			return;
		}

		// Calculate Weight
		let weight = 0;
		// This depends on how webshop exposes cart items weight. 
		// For now, we fetch from cart totals if available or estimate.
		// Standard ERPNext Quotation has total_weight.
		
		frappe.call({
			method: "erpnext_indonesia_localization.api.shipping.get_shipping_rates",
			args: {
				destination_city: city_id,
				weight: 1000, // Default to 1kg if weight not found
			},
			freeze: true,
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					me.render_logistics_selector(r.message);
				}
			}
		});
	},

	render_logistics_selector: function(rates) {
		const me = this;
		this.clear_logistics_ui();
		
		let options_html = rates.map(rate => `
			<div class="courier-option mb-2 p-2 border rounded shadow-sm" style="cursor:pointer;" data-id="${rate.id}" data-cost="${rate.cost}" data-desc="${rate.description}">
				<div class="d-flex justify-content-between align-items-center">
					<div>
						<strong>${rate.courier} - ${rate.service}</strong><br>
						<small class="text-muted">${rate.description} (${rate.etd} days)</small>
					</div>
					<div class="text-primary font-weight-bold">
						${format_currency(rate.cost, "IDR")}
					</div>
				</div>
			</div>
		`).join("");

		const container = $(`
			<div id="indonesia-logistics-container" class="mt-4 mb-4 frappe-card p-5">
				<h6>${__("Select Shipping Service")}</h6>
				<hr>
				<div class="courier-list">
					${options_html}
				</div>
			</div>
		`);

		// Insert before the payment summary or place order button
		$(".cart-payment-addresses").append(container);

		container.find(".courier-option").click(function() {
			container.find(".courier-option").removeClass("bg-light border-primary");
			$(this).addClass("bg-light border-primary");
			me.apply_shipping_cost($(this).data("id"), $(this).data("cost"), $(this).data("desc"));
		});
	},

	apply_shipping_cost: function(service_id, cost, description) {
		frappe.call({
			method: "erpnext_indonesia_localization.api.shipping.apply_custom_shipping_charge",
			args: {
				cost: cost,
				description: description
			},
			callback: function(r) {
				if (r.message) {
					// Update Payment Summary
					$(".cart-tax-items").html(r.message.total);
					$(".payment-summary").html(r.message.taxes_and_totals);
					
					frappe.show_alert({
						message: __("Shipping method updated: ") + description,
						indicator: 'green'
					});
				}
			}
		});
	},

	clear_logistics_ui: function() {
		$("#indonesia-logistics-container").remove();
	}
};

$(document).ready(() => webshop.indonesia_logistics.init());
