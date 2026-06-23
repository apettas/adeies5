(function ($) {
    'use strict';

    $(document).ready(function () {
        $.datepicker.regional.el = {
            closeText: 'Κλείσιμο',
            prevText: '&#x3C;Προηγ',
            nextText: 'Επομ&#x3E;',
            currentText: 'Σήμερα',
            monthNames: [
                'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος', 'Μάιος', 'Ιούνιος',
                'Ιούλιος', 'Αύγουστος', 'Σεπτέμβριος', 'Οκτώβριος', 'Νοέμβριος', 'Δεκέμβριος',
            ],
            monthNamesShort: ['Ιαν', 'Φεβ', 'Μαρ', 'Απρ', 'Μαι', 'Ιουν', 'Ιουλ', 'Αυγ', 'Σεπ', 'Οκτ', 'Νοε', 'Δεκ'],
            dayNames: ['Κυριακή', 'Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο'],
            dayNamesShort: ['Κυρ', 'Δευ', 'Τρι', 'Τετ', 'Πεμ', 'Παρ', 'Σαβ'],
            dayNamesMin: ['Κυ', 'Δε', 'Τρ', 'Τε', 'Πε', 'Πα', 'Σα'],
            weekHeader: 'Εβδ',
            dateFormat: 'dd/mm/yy',
            firstDay: 1,
            isRTL: false,
            showMonthAfterYear: false,
            yearSuffix: '',
        };

        $.datepicker.setDefaults($.datepicker.regional.el);

        $('.greek-datepicker').datepicker({
            dateFormat: 'dd/mm/yy',
            minDate: 0,
            changeMonth: true,
            changeYear: true,
            showButtonPanel: true,
            yearRange: 'c-1:c+2',
            onSelect: function () {
                $(this).trigger('change');
            },
        });
    });
})(window.jQuery);
