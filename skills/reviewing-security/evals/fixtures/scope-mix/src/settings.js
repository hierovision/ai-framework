const logo = require("./logo");

function renderSettings(user) {
  return {
    header: logo.headerFor(user),
  };
}

module.exports = { renderSettings };
