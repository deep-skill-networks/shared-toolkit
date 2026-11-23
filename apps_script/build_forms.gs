/**
 * Build a Google Forms quiz from a dsn-quiz JSON file (`dsn-quiz draw ... --out exports`).
 *
 * Setup (once): open https://script.google.com, create a project, paste this file,
 * then run buildQuizFromDriveFile() with the Drive file ID of the JSON and the ID of the
 * batch gradebook spreadsheet. Authorise when asked.
 *
 * What it sets: quiz mode, 1 point per item, correct/incorrect feedback, email collection,
 * one response per Google account, shuffled question order, responses sent to the gradebook.
 * Check in the form's Settings > Quizzes that marks are released immediately (the default).
 */
function buildQuizFromDriveFile(jsonFileId, gradebookSpreadsheetId) {
  var spec = JSON.parse(DriveApp.getFileById(jsonFileId).getBlob().getDataAsString());
  var form = FormApp.create(spec.title);
  form.setDescription(spec.description)
      .setIsQuiz(true)
      .setCollectEmail(true)
      .setLimitOneResponsePerUser(true)
      .setShuffleQuestions(true)
      .setConfirmationMessage('Submitted. Use "View score" to see your result and the explanations.');

  spec.items.forEach(function (it) {
    var q = form.addMultipleChoiceItem();
    q.setTitle(it.title).setRequired(true).setPoints(it.points || 1);
    q.setChoices(it.choices.map(function (c) { return q.createChoice(c.text, c.isCorrect); }));
    q.setFeedbackForCorrect(FormApp.createFeedback().setText(it.feedbackCorrect).build());
    q.setFeedbackForIncorrect(FormApp.createFeedback().setText(it.feedbackIncorrect).build());
  });

  if (gradebookSpreadsheetId) {
    form.setDestination(FormApp.DestinationType.SPREADSHEET, gradebookSpreadsheetId);
  }
  Logger.log('Edit: ' + form.getEditUrl());
  Logger.log('Share with learners: ' + form.getPublishedUrl());
  return form.getPublishedUrl();
}
