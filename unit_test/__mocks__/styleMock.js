module.exports = new Proxy(
  {},
  {
    get: (_, property) => String(property)
  }
);
