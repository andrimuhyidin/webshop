# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import cint, cstr
from redis.commands.search.query import Query

from webshop.webshop.redisearch_utils import (
	WEBSITE_ITEM_CATEGORY_AUTOCOMPLETE,
	WEBSITE_ITEM_INDEX,
	WEBSITE_ITEM_NAME_AUTOCOMPLETE,
	is_redisearch_enabled,
)
from webshop.webshop.shopping_cart.product_info import set_product_info_for_website
from webshop.webshop.doctype.override_doctype.item_group import get_item_for_list_in_html

no_cache = 1


def get_context(context):
	context.show_search = True


@frappe.whitelist(allow_guest=True)
def get_product_list(search=None, start=0, limit=12):
	data = get_product_data(search, start, limit)

	for item in data:
		set_product_info_for_website(item)

	return [get_item_for_list_in_html(r) for r in data]


def get_product_data(search=None, start=0, limit=12):
	"""Get product data using QueryBuilder for better maintainability."""
	# limit = 12 because we show 12 items in the grid view
	WebsiteItem = frappe.qb.DocType("Website Item")

	query = (
		frappe.qb.from_(WebsiteItem)
		.select(
			WebsiteItem.web_item_name,
			WebsiteItem.item_name,
			WebsiteItem.item_code,
			WebsiteItem.brand,
			WebsiteItem.route,
			WebsiteItem.website_image,
			WebsiteItem.thumbnail,
			WebsiteItem.item_group,
			WebsiteItem.description,
			WebsiteItem.web_long_description.as_("website_description"),
			WebsiteItem.website_warehouse,
			WebsiteItem.ranking,
		)
		.where(WebsiteItem.published == 1)
	)

	# search term condition
	if search:
		search_term = "%" + cstr(search) + "%"
		query = query.where(
			(WebsiteItem.item_name.like(search_term))
			| (WebsiteItem.web_item_name.like(search_term))
			| (WebsiteItem.brand.like(search_term))
			| (WebsiteItem.web_long_description.like(search_term))
		)

	# order by and pagination
	query = (
		query
		.orderby(WebsiteItem.ranking, order=frappe.qb.desc)
		.orderby(WebsiteItem.modified, order=frappe.qb.desc)
		.limit(cint(limit))
		.offset(cint(start))
	)

	return query.run(as_dict=True)


@frappe.whitelist(allow_guest=True)
def search(query):
	product_results = product_search(query)
	category_results = get_category_suggestions(query)

	return {
		"product_results": product_results.get("results") or [],
		"category_results": category_results.get("results") or [],
	}


@frappe.whitelist(allow_guest=True)
def product_search(query, limit=10, fuzzy_search=True):
	search_results = {"from_redisearch": True, "results": []}

	if not is_redisearch_enabled():
		# Redisearch module not enabled
		search_results["from_redisearch"] = False
		search_results["results"] = get_product_data(query, 0, limit)
		return search_results

	if not query:
		return search_results

	redis = frappe.cache()
	query = clean_up_query(query)

	# TODO: Check perf/correctness with Suggestions & Query vs only Query
	# TODO: Use Levenshtein Distance in Query (max=3)
	redisearch = redis.ft(WEBSITE_ITEM_INDEX)
	suggestions = redisearch.sugget(
		WEBSITE_ITEM_NAME_AUTOCOMPLETE,
		query,
		num=limit,
		fuzzy=fuzzy_search and len(query) > 3,
	)

	# Build a query
	query_string = query

	for s in suggestions:
		query_string += f"|('{clean_up_query(s.string)}')"

	q = Query(query_string)
	results = redisearch.search(q)

	search_results["results"] = list(map(convert_to_dict, results.docs))
	search_results["results"] = sorted(
		search_results["results"], key=lambda k: frappe.utils.cint(k["ranking"]), reverse=True
	)

	return search_results


def clean_up_query(query):
	return "".join(c for c in query if c.isalnum() or c.isspace())


def convert_to_dict(redis_search_doc):
	return redis_search_doc.__dict__


@frappe.whitelist(allow_guest=True)
def get_category_suggestions(query):
	search_results = {"results": []}

	if not is_redisearch_enabled():
		# Redisearch module not enabled, query db
		categories = frappe.db.get_all(
			"Item Group",
			filters={"name": ["like", "%{0}%".format(query)], "show_in_website": 1},
			fields=["name", "route"],
		)
		search_results["results"] = categories
		return search_results

	if not query:
		return search_results

	ac = frappe.cache().ft()
	suggestions = ac.sugget(WEBSITE_ITEM_CATEGORY_AUTOCOMPLETE, query, num=10, with_payloads=True)

	results = [json.loads(s.payload) for s in suggestions]

	search_results["results"] = results

	return search_results
