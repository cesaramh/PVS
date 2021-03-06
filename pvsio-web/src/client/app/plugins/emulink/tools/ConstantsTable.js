/**
 * @author Paolo Masci
 * @date May 12, 2017
 */
/*jslint vars: true, plusplus: true, devel: true, nomen: true, indent: 4, maxerr: 50*/
/*global define*/
define(function (require, exports, module) {
    "use strict";

    var Table = require("plugins/emulink/tools/GenericTable"),
        table_element = require("text!plugins/emulink/tools/tables/table_element.handlebars");

    var table;
    var table_name = "Constants";
    var attributes = [
        { name: "Constant Name" },
        { name: "Constant Type" },
        { name: "Initial Value" }
    ];
    function add(e) {
        return Handlebars.compile(table_element, { noEscape: true })({
            table_name: table_name,
            attributes: [
                { name: e.name },
                { name: e.type },
                { name: e.value }
            ]
        });
    }

    function ConstantsTable(div) {
        if (!table) {
            table = new Table(table_name, div, attributes, add);
        }
        return table;
    }

    ConstantsTable.prototype.createHtmlElements = function () {
        table.createHtmlElements();
    };

    module.exports = ConstantsTable;
});
