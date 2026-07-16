/**
 * STRONGSVILLE NEWSLETTER - SUBSCRIBER BACKEND
 * -------------------------------------------------
 * This runs as a free Google Apps Script Web App and does two jobs:
 *   1. Accepts new signups (POST) from your signup.html page and writes
 *      them into a Google Sheet.
 *   2. Returns the list of confirmed subscriber emails (GET, with a
 *      secret key) so the weekly Python script knows who to email.
 *
 * SETUP:
 *   1. Go to https://sheets.google.com and create a new Sheet.
 *      Name the first tab "Subscribers". Add header row: Email | SignupDate | Status
 *      Add a second tab named "Tips". Add header row: Timestamp | Tip | Link | Submitted By
 *      (The "Tips" tab gets filled automatically once you link a Google Form to it - see README.)
 *   2. In the Sheet, go to Extensions > Apps Script.
 *   3. Delete the placeholder code and paste this whole file in.
 *   4. Set SECRET_KEY below to any random string you make up.
 *   5. Click Deploy > New deployment > type "Web app".
 *        - Execute as: Me
 *        - Who has access: Anyone
 *   6. Copy the deployment URL - this is your APPS_SCRIPT_URL.
 *      You'll paste it into signup.html and into your GitHub secrets.
 */

const SECRET_KEY = "trailhead-strongsville-8k2m9x";";
const SHEET_NAME = "Subscribers";
const TIPS_SHEET_NAME = "Tips";

function doPost(e) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const params = JSON.parse(e.postData.contents);
  const email = (params.email || "").trim().toLowerCase();

  if (!email || !email.includes("@")) {
    return jsonResponse({ success: false, message: "Invalid email address." });
  }

  // Avoid duplicate signups
  const existing = sheet.getDataRange().getValues();
  for (let i = 1; i < existing.length; i++) {
    if (existing[i][0] === email) {
      return jsonResponse({ success: true, message: "You're already subscribed!" });
    }
  }

  sheet.appendRow([email, new Date(), "active"]);
  return jsonResponse({ success: true, message: "Subscribed! Welcome to the newsletter." });
}

function doGet(e) {
  const key = e.parameter.key;
  if (key !== SECRET_KEY) {
    return jsonResponse({ success: false, message: "Unauthorized" });
  }

  // ?type=tips returns reader-submitted tips from the last 9 days
  // (e.g. things people spotted on Facebook and forwarded via the tip form).
  if (e.parameter.type === "tips") {
    return jsonResponse({ success: true, tips: getRecentTips() });
  }

  // Default: return the active subscriber list, used by the weekly Python script.
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  const emails = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][2] === "active" && data[i][0]) {
      emails.push(data[i][0]);
    }
  }
  return jsonResponse({ success: true, emails: emails });
}

function getRecentTips() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(TIPS_SHEET_NAME);
  if (!sheet) return [];
  const data = sheet.getDataRange().getValues();
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 9);

  const tips = [];
  for (let i = 1; i < data.length; i++) {
    const [timestamp, tip, link, submittedBy] = data[i];
    if (!tip) continue;
    if (timestamp instanceof Date && timestamp < cutoff) continue;
    tips.push({ tip: String(tip), link: String(link || ""), submitted_by: String(submittedBy || "") });
  }
  return tips;
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
