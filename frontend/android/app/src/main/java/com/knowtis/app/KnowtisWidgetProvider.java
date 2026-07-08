package com.knowtis.app;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class KnowtisWidgetProvider extends AppWidgetProvider {

    private static final String TAG = "KnowtisWidget";
    private static final String SHARED_PREFS_FILE = "knowtis_widget_prefs";
    private static final String KEY_TOKEN = "knowtis_token";
    private static final String KEY_BASE_URL = "knowtis_base_url";
    private static final String FALLBACK_BASE_URL = "https://knowtis-backend.onrender.com/api/v1";
    private static final String WIDGET_ENDPOINT = "/widgets/android";

    private static final ExecutorService executor = Executors.newSingleThreadExecutor();
    private static final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    public void onUpdate(Context context, AppWidgetManager appWidgetManager, int[] appWidgetIds) {
        for (int appWidgetId : appWidgetIds) {
            updateWidget(context, appWidgetManager, appWidgetId);
        }
    }

    /** Allow the Capacitor plugin to push a refresh after the user signs in. */
    static void refreshAll(Context context) {
        AppWidgetManager awm = AppWidgetManager.getInstance(context);
        ComponentName comp = new ComponentName(context, KnowtisWidgetProvider.class);
        int[] ids = awm.getAppWidgetIds(comp);
        if (ids == null) return;
        for (int id : ids) {
            refreshOne(context, awm, id);
        }
    }

    private static void refreshOne(Context context, AppWidgetManager awm, int id) {
        Intent intent = new Intent(context, KnowtisWidgetProvider.class);
        intent.setAction(AppWidgetManager.ACTION_APPWIDGET_UPDATE);
        intent.putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, new int[]{id});
        intent.setData(Uri.parse("kw://update/" + id)); // make the intent unique per id
        context.sendBroadcast(intent);
    }

    private void updateWidget(final Context context, final AppWidgetManager appWidgetManager, final int appWidgetId) {
        final RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.knowtis_widget);
        setClickPendingIntent(context, views);

        final SharedPreferences prefs = context.getSharedPreferences(SHARED_PREFS_FILE, Context.MODE_PRIVATE);
        String token = prefs.getString(KEY_TOKEN, null);
        String baseUrl = prefs.getString(KEY_BASE_URL, FALLBACK_BASE_URL);
        final String endpoint = normalizeEndpoint(baseUrl);

        if (token == null || token.isEmpty()) {
            showEmptyState(views, appWidgetManager, appWidgetId, "Open Knowtis to sign in");
            return;
        }

        final String authToken = token;
        executor.execute(() -> {
            try {
                String response = fetchWidgetData(endpoint, authToken);
                if (response != null) {
                    JSONObject data = new JSONObject(response);
                    final RemoteViews populated = renderWidgetData(context, data);
                    setClickPendingIntent(context, populated);
                    mainHandler.post(() -> appWidgetManager.updateAppWidget(appWidgetId, populated));
                } else {
                    showEmptyState(views, appWidgetManager, appWidgetId, "Couldn't reach Knowtis");
                }
            } catch (Exception e) {
                Log.e(TAG, "Error fetching widget data", e);
                showEmptyState(views, appWidgetManager, appWidgetId, "Couldn't reach Knowtis");
            }
        });
    }

    private String normalizeEndpoint(String baseUrl) {
        if (baseUrl == null || baseUrl.trim().isEmpty()) return FALLBACK_BASE_URL + WIDGET_ENDPOINT;
        String b = baseUrl.trim();
        if (b.endsWith("/")) b = b.substring(0, b.length() - 1);
        if (!b.endsWith("/api/v1")) {
            // If only the host was stored, append the api path.
            if (b.contains("/api/v")) {
                return b + WIDGET_ENDPOINT;
            }
            return b + "/api/v1" + WIDGET_ENDPOINT;
        }
        return b + WIDGET_ENDPOINT;
    }

    private void showEmptyState(RemoteViews views, AppWidgetManager appWidgetManager, int appWidgetId, String message) {
        views.setViewVisibility(R.id.widget_content, View.GONE);
        views.setViewVisibility(R.id.widget_type_label, View.GONE);
        views.setViewVisibility(R.id.widget_empty, View.VISIBLE);
        views.setTextViewText(R.id.widget_empty, message);
        appWidgetManager.updateAppWidget(appWidgetId, views);
    }

    private String fetchWidgetData(String endpoint, String token) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(endpoint);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Authorization", "Bearer " + token);
            conn.setRequestProperty("Accept", "application/json");
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(8000);

            int responseCode = conn.getResponseCode();
            if (responseCode != HttpURLConnection.HTTP_OK) {
                Log.w(TAG, "Widget API returned: " + responseCode);
                return null;
            }

            BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
            reader.close();
            return sb.toString();
        } catch (Exception e) {
            Log.e(TAG, "Network error", e);
            return null;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private RemoteViews renderWidgetData(Context context, JSONObject response) throws Exception {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.knowtis_widget);
        setClickPendingIntent(context, views);

        // The backend may return either a bare widget object or wrap it in a data envelope.
        JSONObject data = response.optJSONObject("data");
        if (data == null) data = response;

        JSONObject dailyBrief = data.optJSONObject("daily_brief");
        int deadlinesToday = dailyBrief != null ? dailyBrief.optInt("deadlines_today", 0) : 0;

        views.setTextViewText(R.id.widget_count, String.valueOf(deadlinesToday));
        views.setTextViewText(R.id.widget_count_label,
                deadlinesToday == 1 ? "deadline today" : "deadlines today");
        views.setViewVisibility(R.id.widget_type_label, View.VISIBLE);
        views.setTextViewText(R.id.widget_type_label, "Daily Brief");

        JSONArray cascadeEvents = data.optJSONArray("cascade_events");
        boolean hasEvents = cascadeEvents != null && cascadeEvents.length() > 0;

        if (hasEvents) {
            views.setViewVisibility(R.id.widget_content, View.VISIBLE);
            views.setViewVisibility(R.id.widget_empty, View.GONE);

            int eventCount = Math.min(cascadeEvents.length(), 2);
            for (int i = 0; i < eventCount; i++) {
                JSONObject event = cascadeEvents.getJSONObject(i);
                String eventType = event.optString("event_type", "").toUpperCase(Locale.ROOT);
                String title = event.optString("title", "");
                String venue = event.optString("venue", null);
                String dateTimeStr = event.optString("date_time", null);
                String meta = formatEventMeta(dateTimeStr, venue);

                int typeTextId = (i == 0) ? R.id.widget_item1_type_text : R.id.widget_item2_type_text;
                int titleId = (i == 0) ? R.id.widget_item1_title : R.id.widget_item2_title;
                int metaId = (i == 0) ? R.id.widget_item1_meta : R.id.widget_item2_meta;
                views.setTextViewText(typeTextId, eventType.isEmpty() ? "EVENT" : eventType);
                views.setTextColor(typeTextId, getEventTypeColor(eventType));
                views.setTextViewText(titleId, title.isEmpty() ? "Untitled" : title);
                views.setTextViewText(metaId, meta);
            }
            if (eventCount < 2) {
                views.setViewVisibility(R.id.widget_event2, View.GONE);
            }
        } else {
            views.setViewVisibility(R.id.widget_content, View.VISIBLE);
            views.setViewVisibility(R.id.widget_empty, View.GONE);
            views.setViewVisibility(R.id.widget_event1, View.GONE);
            views.setViewVisibility(R.id.widget_event2, View.GONE);
            views.setTextViewText(R.id.widget_count, "0");
            views.setTextViewText(R.id.widget_count_label, "No upcoming events");
        }

        return views;
    }

    private String formatEventMeta(String dateTimeStr, String venue) {
        StringBuilder sb = new StringBuilder();
        if (dateTimeStr != null && !dateTimeStr.isEmpty()) {
            try {
                String cleaned = dateTimeStr.replaceFirst("\\+.*$", "").replaceFirst("Z$", "");
                SimpleDateFormat isoFormat = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US);
                Date date = isoFormat.parse(cleaned);
                if (date != null) {
                    sb.append(new SimpleDateFormat("EEE d", Locale.US).format(date));
                    sb.append(" · ").append(new SimpleDateFormat("HH:mm", Locale.US).format(date));
                } else {
                    sb.append(dateTimeStr);
                }
            } catch (Exception e) {
                sb.append(dateTimeStr);
            }
        }
        if (venue != null && !venue.isEmpty()) {
            if (sb.length() > 0) sb.append(" · ");
            sb.append(venue);
        }
        return sb.length() > 0 ? sb.toString() : "No details";
    }

    private int getEventTypeColor(String eventType) {
        switch (eventType) {
            case "DEADLINE":
                return 0xFFFF5A36;
            case "ALERT":
                return 0xFFDC2626;
            case "EVENT":
                return 0xFF4285F4;
            case "INFO":
                return 0xFF7C3AED;
            default:
                return 0xFF686862;
        }
    }

    private void setClickPendingIntent(Context context, RemoteViews views) {
        Intent intent = new Intent(context, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        views.setOnClickPendingIntent(R.id.knowtis_widget_root, pendingIntent);
    }
}
