package az.hug.assistant;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.telecom.PhoneAccount;
import android.telecom.PhoneAccountHandle;
import android.telecom.TelecomManager;
import android.telephony.SubscriptionInfo;
import android.telephony.SubscriptionManager;
import android.telephony.TelephonyManager;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Places a phone call directly (no dialer step). HUG only calls this AFTER the user has
 * confirmed ("Bəli") in the app, so the human-in-the-loop rule still holds.
 * Falls back to opening the dialer if the permission is refused.
 *
 * Dual-SIM phones: simCards() lists the SIMs that can call, so the assistant can ask
 * "SIM 1 or SIM 2?" by voice; call({ number, sim }) then places the call on that SIM and
 * Android's own SIM picker never appears.
 */
@CapacitorPlugin(
    name = "DirectCall",
    permissions = {
        @Permission(alias = "call", strings = { Manifest.permission.CALL_PHONE }),
        @Permission(alias = "phone", strings = { Manifest.permission.READ_PHONE_STATE })
    }
)
public class DirectCallPlugin extends Plugin {

    /** A call-capable SIM: its telecom handle plus what to say to the user. */
    private static final class Sim {
        final PhoneAccountHandle handle;
        final int slot;          // 1-based SIM slot, or 0 when unknown
        final String carrier;    // e.g. "Azercell"

        Sim(PhoneAccountHandle handle, int slot, String carrier) {
            this.handle = handle;
            this.slot = slot;
            this.carrier = carrier;
        }
    }

    // ---------------------------------------------------------------- SIM list

    @PluginMethod
    public void simCards(PluginCall call) {
        if (getPermissionState("phone") != PermissionState.GRANTED) {
            requestPermissionForAlias("phone", call, "simPermissionCallback");
            return;
        }
        resolveSims(call);
    }

    @PermissionCallback
    private void simPermissionCallback(PluginCall call) {
        resolveSims(call); // without the permission the list is simply empty
    }

    private void resolveSims(PluginCall call) {
        JSArray list = new JSArray();
        List<Sim> sims = listSims();
        for (int i = 0; i < sims.size(); i++) {
            Sim s = sims.get(i);
            JSObject o = new JSObject();
            o.put("index", i);
            o.put("slot", s.slot > 0 ? s.slot : i + 1);
            o.put("carrier", s.carrier == null ? "" : s.carrier);
            list.put(o);
        }
        JSObject ret = new JSObject();
        ret.put("sims", list);
        call.resolve(ret);
    }

    private List<Sim> listSims() {
        List<Sim> sims = new ArrayList<>();
        if (getPermissionState("phone") != PermissionState.GRANTED) return sims;
        Context ctx = getContext();
        TelecomManager telecom = (TelecomManager) ctx.getSystemService(Context.TELECOM_SERVICE);
        if (telecom == null) return sims;

        List<PhoneAccountHandle> handles;
        try {
            handles = telecom.getCallCapablePhoneAccounts();
        } catch (SecurityException e) {
            return sims;
        }
        if (handles == null) return sims;

        TelephonyManager tm = (TelephonyManager) ctx.getSystemService(Context.TELEPHONY_SERVICE);
        SubscriptionManager sm = (SubscriptionManager) ctx.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE);

        for (PhoneAccountHandle h : handles) {
            int slot = 0;
            String carrier = null;
            // Android 11+: map the telecom account to its SIM subscription (slot + carrier name)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && tm != null && sm != null) {
                try {
                    int subId = tm.getSubscriptionId(h);
                    SubscriptionInfo info = sm.getActiveSubscriptionInfo(subId);
                    if (info != null) {
                        slot = info.getSimSlotIndex() + 1;
                        CharSequence name = info.getCarrierName();
                        if (name == null || name.length() == 0) name = info.getDisplayName();
                        if (name != null) carrier = name.toString();
                    }
                } catch (Exception ignored) { /* fall back to the account label */ }
            }
            if (carrier == null) {
                try {
                    PhoneAccount account = telecom.getPhoneAccount(h);
                    if (account != null && account.getLabel() != null) carrier = account.getLabel().toString();
                } catch (Exception ignored) { }
            }
            sims.add(new Sim(h, slot, carrier));
        }
        // Speak them in slot order: "SIM 1 ..., SIM 2 ..."
        Collections.sort(sims, (a, b) -> Integer.compare(a.slot == 0 ? 99 : a.slot, b.slot == 0 ? 99 : b.slot));
        return sims;
    }

    // ---------------------------------------------------------------- calls

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
        Uri uri = Uri.parse("tel:" + clean);

        // A chosen SIM: place the call on that account so Android's SIM picker is skipped
        Integer simIndex = call.getInt("sim");
        if (direct && simIndex != null) {
            List<Sim> sims = listSims();
            if (simIndex >= 0 && simIndex < sims.size()) {
                try {
                    TelecomManager telecom = (TelecomManager) getContext().getSystemService(Context.TELECOM_SERVICE);
                    Bundle extras = new Bundle();
                    extras.putParcelable(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, sims.get(simIndex).handle);
                    telecom.placeCall(uri, extras);
                    JSObject ret = new JSObject();
                    ret.put("direct", true);
                    ret.put("sim", simIndex);
                    call.resolve(ret);
                    return;
                } catch (Exception ignored) { /* fall through to the plain call intent */ }
            }
        }

        Intent intent = new Intent(direct ? Intent.ACTION_CALL : Intent.ACTION_DIAL, uri);
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
