(function () {
    'use strict';

    const body = document.body;
    const csrfToken = body.dataset.csrfToken || '';
    const notificationsApi = body.dataset.notificationsApi || '';
    const markAllReadUrl = body.dataset.markAllReadUrl || '';
    const isAuthenticated = body.dataset.userAuthenticated === 'true';

    function syncMobileNotifBadge(count) {
        const mobileBadge = document.getElementById('mobile-notif-badge');
        if (!mobileBadge) {
            return;
        }
        if (count > 0) {
            mobileBadge.textContent = count > 9 ? '9+' : count;
            mobileBadge.classList.remove('d-none');
        } else {
            mobileBadge.classList.add('d-none');
        }
    }

    function loadNotifications() {
        if (!notificationsApi) {
            return;
        }
        fetch(notificationsApi)
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                const notificationList = document.getElementById('notification-list');
                const notificationCount = document.getElementById('notification-count');
                if (!notificationList || !notificationCount) {
                    return;
                }

                if (data.unread_count > 0) {
                    notificationCount.textContent = data.unread_count;
                    notificationCount.classList.remove('d-none');
                } else {
                    notificationCount.classList.add('d-none');
                }
                syncMobileNotifBadge(data.unread_count);

                if (data.notifications.length > 0) {
                    notificationList.innerHTML = data.notifications.map(function (notification) {
                        return (
                            '<li>' +
                            '<a class="dropdown-item ' + (notification.is_read ? '' : 'fw-bold') + '" ' +
                            'href="#" data-notification-id="' + notification.id + '">' +
                            '<div class="d-flex justify-content-between align-items-start">' +
                            '<div>' +
                            '<div class="fw-bold">' + notification.title + '</div>' +
                            '<small class="text-muted">' + notification.message + '</small>' +
                            '<br><small class="text-muted">' + notification.created_at + '</small>' +
                            '</div>' +
                            '<span class="badge ' + notification.badge_class + '">' + notification.type + '</span>' +
                            '</div>' +
                            '</a>' +
                            '</li>'
                        );
                    }).join('');

                    notificationList.querySelectorAll('[data-notification-id]').forEach(function (link) {
                        link.addEventListener('click', function (event) {
                            event.preventDefault();
                            markAsRead(link.dataset.notificationId);
                        });
                    });
                } else {
                    notificationList.innerHTML =
                        '<li><span class="dropdown-item-text text-muted">Δεν υπάρχουν ειδοποιήσεις</span></li>';
                }
            });
    }

    function markAsRead(notificationId) {
        fetch('/notifications/mark-read/' + notificationId + '/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
        }).then(function () {
            loadNotifications();
        });
    }

    function markAllAsRead() {
        if (!markAllReadUrl) {
            return;
        }
        fetch(markAllReadUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
        }).then(function () {
            loadNotifications();
        });
    }

    function formatGreekDate(date) {
        const days = ['Κυριακή', 'Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο'];
        const months = [
            'Ιανουαρίου', 'Φεβρουαρίου', 'Μαρτίου', 'Απριλίου', 'Μαΐου', 'Ιουνίου',
            'Ιουλίου', 'Αυγούστου', 'Σεπτεμβρίου', 'Οκτωβρίου', 'Νοεμβρίου', 'Δεκεμβρίου',
        ];
        return days[date.getDay()] + ', ' + date.getDate() + ' ' + months[date.getMonth()] + ' ' + date.getFullYear();
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (isAuthenticated) {
            loadNotifications();
            setInterval(loadNotifications, 30000);

            const markAllBtn = document.getElementById('mark-all-notifications-read');
            if (markAllBtn) {
                markAllBtn.addEventListener('click', function (event) {
                    event.preventDefault();
                    markAllAsRead();
                });
            }
        }

        const dateElement = document.getElementById('current-date-greek');
        if (dateElement) {
            dateElement.textContent = formatGreekDate(new Date());
        }
    });
})();
