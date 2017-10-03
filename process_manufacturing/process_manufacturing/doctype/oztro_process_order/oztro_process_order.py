# -*- coding: utf-8 -*-
# Copyright (c) 2017, earthians and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class OztroProcessOrder(Document):
	def get_process_details(self):
		#	Set costing_method
		self.costing_method = frappe.db.get_value("Oztro Process", self.process_name, "costing_method")
		#	Set Child Tables
		process = frappe.get_doc("Oztro Process", self.process_name)
		if process:
			if process.materials:
				add_item_in_table(self, process.materials, "materials")
			if process.finished_products:
				add_item_in_table(self, process.finished_products, "finished_products")
			if process.scrap:
				add_item_in_table(self, process.scrap, "scrap")

	def start_finish_processing(self, status):
		#self.status = status
		#self.save()
		return self.make_stock_entry(status)

	def set_se_items_start(self, se):
		for item in self.materials:
			se = self.set_se_items(se, item, frappe.db.get_value("Item", item.item, "default_warehouse"), se.from_warehouse)
		return se

	def set_se_items_finish(self, se):
		se_materials = frappe.get_doc("Stock Entry",{"oztro_process_order": self.name})
		if se_materials:
			se.items = se_materials.items
			for item in se.items:
				item.s_warehouse = se.from_warehouse
				item.t_warehouse = None
		else:
			for item in self.materials:
				se = self.set_se_items(se, item, se.from_warehouse, None)
		for item in self.finished_products:
			se = self.set_se_items(se, item, None, se.to_warehouse)

		for item in self.scrap:
			se = self.set_se_items(se, item, None, self.scrap_warehouse)

		return se

	def set_se_items(self, se, item, s_wh, t_wh):
		expense_account, cost_center = frappe.db.get_values("Company", self.company, \
				["default_expense_account", "cost_center"])[0]
		item_name, stock_uom, description, item_expense_account, item_cost_center = frappe.db.get_values("Item", item.item, \
		["item_name", "stock_uom", "description", "expense_account", "buying_cost_center"])[0]

		if item.quantity > 0:
			se_item = se.append("items")
			se_item.item_code = item.item
			se_item.qty = item.quantity
			se_item.s_warehouse = s_wh
			se_item.t_warehouse = t_wh
			se_item.item_name = item_name
			se_item.description = description
			se_item.uom = stock_uom
			se_item.stock_uom = stock_uom

			se_item.expense_account = item_expense_account or expense_account
			se_item.cost_center = item_cost_center or cost_center

			# in stock uom
			se_item.transfer_qty = item.quantity
			se_item.conversion_factor = 1.00

		if se.items:
			return se

	def make_stock_entry(self, status):
		if self.wip_warehouse:
			wip_warehouse = self.wip_warehouse
		else:
			wip_warehouse = frappe.db.get_single_value("Manufacturing Settings", "default_wip_warehouse")
		if self.fg_warehouse:
			fg_warehouse = self.fg_warehouse
		else:
			fg_warehouse = frappe.db.get_single_value("Manufacturing Settings", "default_fg_warehouse")

		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Manufacture"
		stock_entry.oztro_process_order = self.name
		stock_entry.from_warehouse = wip_warehouse
		stock_entry.to_warehouse = fg_warehouse
		if status == "Start":
			stock_entry = self.set_se_items_start(stock_entry)
		if status == "Finish":
			stock_entry = self.set_se_items_finish(stock_entry)
		return stock_entry.as_dict()

def add_item_in_table(self, table_value, table_name):
	clear_table(self, table_name)

	for item in table_value:
		po_item = self.append(table_name, {})
		po_item.item = item.item
		po_item.item_name = item.item_name

def clear_table(self, table_name):
	self.set(table_name, [])

@frappe.whitelist()
def submit_se(doc, method):
	if doc.oztro_process_order:
		oztro_po = frappe.get_doc("Oztro Process Order", doc.oztro_process_order)
		if oztro_po.status == "Open":
			oztro_po.status = "Start"
		elif oztro_po.status == "Start":
			oztro_po.status = "Finish"
		oztro_po.save()
