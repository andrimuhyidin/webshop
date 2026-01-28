# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WebsiteOffer(Document):
	"""
	Website Offer for promotional banners and discounts.
	
	Displays promotional offers, discounts, and special deals on
	the website storefront with configurable offer details.
	"""

	pass


@frappe.whitelist(allow_guest=True)
def get_offer_details(offer_id):
	return frappe.db.get_value("Website Offer", {"name": offer_id}, ["offer_details"])
