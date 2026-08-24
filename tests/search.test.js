const assert = require("node:assert/strict");
const { rankSearchDocs, searchSnippet } = require("../static/zola-docs-search.js");

const docs = [
  { title: "Install on Linux", path: "/install/linux/", body: "Download an AppImage." },
  { title: "Configuration", path: "/reference/config/", body: "Configure fonts and keys." },
  { title: "Agent CLI", path: "/cli/agent/", body: "Manage an agent harness." },
];

assert.equal(rankSearchDocs(docs, "download linux")[0].doc.path, "/install/linux/");
assert.equal(rankSearchDocs(docs, "agent harness")[0].doc.path, "/cli/agent/");
assert.deepEqual(rankSearchDocs(docs, "missing"), []);
assert.match(searchSnippet("before before target after after", ["target"], 10), /target/);

console.log("search ranking and snippets: 4 checks passed");
