// ==UserScript==
// @name         League Table Points Calculator
// @namespace    http://tampermonkey.net/
// @version      0.2
// @description  Calculate points required to be top of the league and to reach 6th place
// @author       GitHub Copilot
// @match        http://spacedlevo.pythonanywhere.com/
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  // Wait for the DOM to be fully loaded
  window.addEventListener("load", function () {
    // Get the table with the ID of leaguetable
    var table = document.getElementById("leaguetable");
    if (!table) return;

    // Get the 4th td of the second row to find the amount of points top spot has
    var topPoints = parseInt(table.rows[1].cells[4].innerText);

    // Get the 4th td of the 7th row to find the amount of points 6th place has
    var sixthPlacePoints = parseInt(table.rows[6].cells[4].innerText);

    // Add header cells with the values "To Be Top" and "To Be 6th"
    var headerRow = table.rows[0];
    var newHeaderCellTop = document.createElement("th");
    newHeaderCellTop.innerText = "To Be Top";
    headerRow.appendChild(newHeaderCellTop);

    var newHeaderCellSixth = document.createElement("th");
    newHeaderCellSixth.innerText = "To Be 6th";
    headerRow.appendChild(newHeaderCellSixth);

    // Loop through each row starting from the second row
    for (var i = 1; i < table.rows.length; i++) {
      var row = table.rows[i];
      var currentPoints = parseInt(row.cells[4].innerText);

      // Calculate the points required to be top of the league
      var pointsRequiredTop = topPoints - currentPoints;

      // Calculate the points required to reach 6th place
      var pointsRequiredSixth = sixthPlacePoints - currentPoints;
      if (pointsRequiredSixth < 0) {
        pointsRequiredSixth = 0;
      }

      // Create new cells and add them to the row
      var newCellTop = row.insertCell(-1);
      newCellTop.innerText = pointsRequiredTop;

      var newCellSixth = row.insertCell(-1);
      newCellSixth.innerText = pointsRequiredSixth;
    }
  });
})();
