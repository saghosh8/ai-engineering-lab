// Cart helpers for the demo shop API.
//
// Prices are plain numbers (dollars). Quantities are positive integers.

const TAX_RATE = 0.08;
const FREE_SHIPPING_THRESHOLD = 50;
const BULK_RATE = 0.1;

function round(n) {
  return Math.round(n * 100) / 100;
}

function lineTotal(item) {
  return item.price * item.qty;
}

function total(items) {
  return items.reduce((sum, item) => sum + lineTotal(item), 0);
}

function tax(items) {
  return round(total(items) * TAX_RATE);
}

function shippingCost(items) {
  return total(items) >= FREE_SHIPPING_THRESHOLD ? 0 : 5.99;
}

function itemCount(items) {
  return items.reduce((n, item) => n + item.qty, 0);
}

// Buy-more-save-more: 10% off carts with 3+ items, and the cheapest
// item is free on carts with 5+ items. An empty cart costs nothing, so
// its discounted total is 0.
function bulkDiscountRate(items) {
  return itemCount(items) >= 3 ? BULK_RATE : 0;
}

function applyDiscount(cart) {
  const { items } = cart;
  const cheapest = items.reduce((a, b) => (a.price <= b.price ? a : b));
  const credit = itemCount(items) >= 5 ? cheapest.price : 0;
  return round(total(items) * (1 - bulkDiscountRate(items)) - credit);
}

module.exports = { round, total, tax, shippingCost, itemCount, bulkDiscountRate, applyDiscount };
