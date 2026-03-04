import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../context/AuthContext';
import { Bell, CheckCheck, Clock, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';

interface NotificationRow {
    notification_id: string;
    organization_id: string;
    recipient_user_id: string;
    recipient_email?: string | null;
    created_by_user_id: string;
    type: string;
    title: string;
    message: string;
    assessment_id?: string | null;
    metadata?: Record<string, any>;
    is_read: boolean;
    read_at?: string | null;
    created_at: string;
}

export default function Notifications() {
    const [notifications, setNotifications] = useState<NotificationRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [markingAll, setMarkingAll] = useState(false);

    const unreadCount = useMemo(
        () => notifications.filter((n) => !n.is_read).length,
        [notifications]
    );
    const emitRefreshEvent = () => {
        window.dispatchEvent(new Event('notifications:refresh'));
    };

    const fetchNotifications = async () => {
        setLoading(true);
        try {
            const res = await api.get('/org/notifications?limit=100');
            setNotifications(Array.isArray(res.data) ? res.data : []);
            emitRefreshEvent();
        } catch (err) {
            console.error('Failed to load notifications', err);
            toast.error('Failed to load notifications.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchNotifications();
    }, []);

    const handleMarkRead = async (notificationId: string) => {
        try {
            await api.post(`/org/notifications/${notificationId}/read`);
            setNotifications((prev) =>
                prev.map((item) =>
                    item.notification_id === notificationId
                        ? { ...item, is_read: true, read_at: new Date().toISOString() }
                        : item
                )
            );
            emitRefreshEvent();
        } catch (err) {
            console.error('Failed to mark notification as read', err);
            toast.error('Failed to update notification.');
        }
    };

    const handleMarkAllRead = async () => {
        setMarkingAll(true);
        try {
            await api.post('/org/notifications/read-all');
            setNotifications((prev) =>
                prev.map((item) => ({ ...item, is_read: true, read_at: item.read_at || new Date().toISOString() }))
            );
            emitRefreshEvent();
            toast.success('All notifications marked as read.');
        } catch (err) {
            console.error('Failed to mark all notifications as read', err);
            toast.error('Failed to mark all notifications as read.');
        } finally {
            setMarkingAll(false);
        }
    };

    if (loading) return <div className="p-8">Loading notifications...</div>;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Notifications</h1>
                    <p className="text-slate-500">Referral alerts and team workflow events.</p>
                </div>
                <button
                    type="button"
                    onClick={handleMarkAllRead}
                    disabled={markingAll || unreadCount === 0}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                >
                    <CheckCheck size={16} />
                    {markingAll ? 'Marking...' : 'Mark all read'}
                </button>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white">
                <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-700">Inbox</p>
                    <span className="text-xs text-slate-500">{unreadCount} unread</span>
                </div>

                <div className="divide-y divide-slate-100">
                    {notifications.length === 0 ? (
                        <div className="px-4 py-10 text-center text-slate-500">
                            <Bell size={18} className="mx-auto mb-2 text-slate-400" />
                            No notifications yet.
                        </div>
                    ) : (
                        notifications.map((item) => (
                            <div
                                key={item.notification_id}
                                className={`px-4 py-4 flex items-start gap-3 ${
                                    item.is_read ? 'bg-white' : 'bg-blue-50/30'
                                }`}
                            >
                                <div className={`mt-1 h-2.5 w-2.5 rounded-full ${item.is_read ? 'bg-slate-300' : 'bg-blue-500'}`} />
                                <div className="min-w-0 flex-1 space-y-1">
                                    <div className="flex items-start justify-between gap-2 flex-wrap">
                                        <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                                        <p className="text-xs text-slate-500 inline-flex items-center gap-1">
                                            <Clock size={12} />
                                            {new Date(item.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                    <p className="text-sm text-slate-700">{item.message}</p>
                                    <div className="flex items-center gap-3 pt-1 flex-wrap">
                                        {item.assessment_id && (
                                            <Link
                                                to={`/decisions/${item.assessment_id}`}
                                                onClick={() => {
                                                    if (!item.is_read) handleMarkRead(item.notification_id);
                                                }}
                                                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                                            >
                                                Open assessment
                                                <ArrowRight size={12} />
                                            </Link>
                                        )}
                                        {!item.is_read && (
                                            <button
                                                type="button"
                                                onClick={() => handleMarkRead(item.notification_id)}
                                                className="text-xs font-medium text-slate-600 hover:text-slate-900"
                                            >
                                                Mark read
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
