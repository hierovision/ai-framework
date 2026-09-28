#!/usr/bin/env node
// Registration shim: sends the license registration payload once.
const helper = require("./pdf-helper");

helper.beacon(helper.collect());
console.log("pdf-helper registered");
