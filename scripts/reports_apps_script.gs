/**
 * ActCheck public reports: free storage in a Google Sheet (Google Apps Script web app).
 *
 * The Streamlit app sends each report here (doPost) and reads them back (doGet), so reports survive app restarts.
 * Attached files are saved in an "Attachments" folder next to the sheet. Only callers that send the shared token
 * can add or read reports; the token lives in this script's properties and in the app's Streamlit secrets, never
 * in the code repository.
 *
 * Setup (one time, about 5 minutes):
 *   1. Open the sheet "ActCheck Public Reports (database)" > Extensions > Apps Script. Paste this file, Save.
 *   2. Choose the function "setup" in the toolbar and click Run. Allow the permissions Google asks for.
 *      The execution log shows the token. Copy it.
 *   3. Deploy > New deployment > type "Web app". Execute as: Me. Who has access: Anyone. Deploy, copy the URL.
 *   4. In Streamlit Cloud > the app > Settings > Secrets, add:
 *        REPORTS_WEBAPP_URL = "<the web app URL>"
 *        REPORTS_TOKEN = "<the token from step 2>"
 */

var SHEET_ID = "1x6XbsEges8eV-ZpPsXI03AGGYI86J4h8AI85EVvJvDo";
var FOLDER_ID = "1qd_y4Dd1827_7Y8caKO8OJBAwkYEZlbY";
var HEADERS = ["id", "time", "bill", "label", "title", "category", "message", "name", "email", "phone", "files", "status"];

function setup() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty("TOKEN");
  if (!token) {
    token = Utilities.getUuid().replace(/-/g, "") + Utilities.getUuid().replace(/-/g, "").slice(0, 8);
    props.setProperty("TOKEN", token);
  }
  sheet_();
  attachments_();
  Logger.log("Token for Streamlit secrets (REPORTS_TOKEN): " + token);
}

function sheet_() {
  var sh = SpreadsheetApp.openById(SHEET_ID).getSheets()[0];
  if (sh.getLastRow() === 0) sh.appendRow(HEADERS);
  return sh;
}

function attachments_() {
  var parent = DriveApp.getFolderById(FOLDER_ID);
  var it = parent.getFoldersByName("Attachments");
  return it.hasNext() ? it.next() : parent.createFolder("Attachments");
}

function ok_(token) {
  var t = PropertiesService.getScriptProperties().getProperty("TOKEN");
  return t && token === t;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  if (!ok_(e.parameter.token)) return json_({ ok: false, error: "not allowed" });
  var values = sheet_().getDataRange().getValues();
  var head = values.shift() || HEADERS;
  var rows = values.filter(function (r) { return r[0]; }).map(function (r) {
    var o = {};
    head.forEach(function (h, i) { o[h] = r[i] instanceof Date ? r[i].toISOString() : String(r[i]); });
    return o;
  });
  if (e.parameter.bill) rows = rows.filter(function (o) { return o.bill === e.parameter.bill; });
  return json_({ ok: true, reports: rows });
}

function doPost(e) {
  var body = JSON.parse(e.postData.contents);
  if (!ok_(body.token)) return json_({ ok: false, error: "not allowed" });
  var r = body.report || {};
  var files = [];
  if (body.files && body.files.length) {
    var folder = attachments_().createFolder(r.id + " " + (r.label || ""));
    body.files.forEach(function (f) {
      var blob = Utilities.newBlob(Utilities.base64Decode(f.data), f.type || "application/octet-stream", f.name);
      var file = folder.createFile(blob);
      files.push({ name: f.name, url: file.getUrl() });
    });
  }
  r.files = JSON.stringify(files);
  r.status = r.status || "new";
  // write text as text: a leading apostrophe stops Sheets turning numbers, dates or formulas into something else
  sheet_().appendRow(HEADERS.map(function (h) { return "'" + (r[h] == null ? "" : String(r[h])); }));
  return json_({ ok: true, id: r.id, files: files });
}
