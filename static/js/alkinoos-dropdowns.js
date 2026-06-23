(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        if (typeof bootstrap !== 'undefined' && bootstrap.Dropdown) {
            document.querySelectorAll('.dropdown-toggle').forEach(function (toggle) {
                new bootstrap.Dropdown(toggle);
            });
        }
    });
})();
