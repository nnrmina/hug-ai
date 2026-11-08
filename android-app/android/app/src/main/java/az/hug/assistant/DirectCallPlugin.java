package az.hug.assistant;

import android.Manifest;
import android.content.Intent;
import android.net.Uri;

import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

/**
 * Places a phone call directly (no dialer step). HUG only calls this AFTER the user has
 * confirmed ("Bəli") in the app, so the human-in-the-loop rule still holds.
 * Falls back to opening the dialer if the permission is refused.
 */
@CapacitorPlugin(
    name = "DirectCall",
    permissions = { @Permission(alias = "call", strings = { Manifest.permission.CALL_PHONE }) }
)
public class DirectCallPlugin extends Plugin {

    @PluginMethod
    public void call(PluginCall call) {
        String number = call.getString("number");
        if (number == null || number.trim().isEmpty()) {
            call.reject("number is required");
            return;
        }
        if (getPermissionState("call") != PermissionState.GRANTED) {
            requestPermissionForAlias("call", call, "callPermissionCallback");
            return;
        }
        placeCall(call, number, true);
    }

    @PermissionCallback
    private void callPermissionCallback(PluginCall call) {
        boolean granted = getPermissionState("call") == PermissionState.GRANTED;
        placeCall(call, call.getString("number"), granted);
    }

    private void placeCall(PluginCall call, String number, boolean direct) {
        String clean = number.replaceAll("[^0-9+]", "");
        Intent intent = new Intent(direct ? Intent.ACTION_CALL : Intent.ACTION_DIAL, Uri.parse("tel:" + clean));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            getActivity().startActivity(intent);
            JSObject ret = new JSObject();
            ret.put("direct", direct);
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("Could not start call: " + e.getMessage());
        }
    }
}
