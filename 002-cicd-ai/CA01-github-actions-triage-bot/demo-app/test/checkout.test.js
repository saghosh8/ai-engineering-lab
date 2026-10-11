const { total, tax, shippingCost, applyDiscount } = require("../src/cart");

const book = { sku: "book", price: 12.5, qty: 1 };
const pen = { sku: "pen", price: 2, qty: 3 };

describe("checkout", () => {
  test("totals the line items", () => {
    expect(total([book, pen])).toBe(18.5);
  });

  test("adds sales tax", () => {
    expect(tax([book, pen])).toBe(1.48);
  });

  test("charges shipping under the free threshold", () => {
    expect(shippingCost([book, pen])).toBe(5.99);
  });

  test("gives 10% off a cart with three or more items", () => {
    expect(applyDiscount({ items: [book, pen] })).toBe(16.65);
  });

  test("makes the cheapest item free on five or more items", () => {
    const cheapPens = { sku: "pen", price: 2, qty: 4 };
    expect(applyDiscount({ items: [book, cheapPens] })).toBe(16.45);
  });

  test("applies discount to empty cart", () => {
    expect(applyDiscount({ items: [] })).toBe(0);
  });
});
