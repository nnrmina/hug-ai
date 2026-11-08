# Yaxın AI — mobile (Flutter, Android)

## Run (debug)

```sh
flutter pub get
flutter run                                   # emulator → http://10.0.2.2:8000/api/v1
flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api/v1   # phone on Wi-Fi
```

Debug builds allow plain HTTP only to `10.0.2.2`, `localhost` and `127.0.0.1`
(`android/app/src/debug/res/xml/network_security_config.xml`). For a phone on
your LAN, add your PC's IP to that file.

Optional: `--dart-define=API_KEY=...` sends `X-API-Key` on every request.

## Authentication

On first start the app calls `POST /api/v1/auth/device` (sending the stored
install UUID as `legacy_user_id`) and stores the returned JWT in
shared_preferences. Every other request sends `Authorization: Bearer <token>`.
On a 401 the token is discarded, the device re-registers once and the request
is retried once.

## Release build

Release builds are **HTTPS only**:

- `android/app/src/main/res/xml/network_security_config.xml` forbids cleartext.
- The app refuses to start (shows a configuration error) if `API_BASE_URL`
  is not `https://` in release mode.

```sh
flutter build apk --release \
  --dart-define=API_BASE_URL=https://api.example.az/api/v1 \
  --dart-define=API_KEY=xxxxx
```

### Signing key (required before publishing)

Without `android/key.properties` the release build falls back to the **debug
key** (a Gradle warning is printed). Never publish such an APK.

1. Create a keystore once and keep it (and its passwords) safe — losing it
   means you can never update the app:

   ```sh
   keytool -genkey -v -keystore %USERPROFILE%\yaxin-release.jks ^
     -keyalg RSA -keysize 2048 -validity 10000 -alias yaxin
   ```

2. Create `android/key.properties` (already git-ignored, never commit it):

   ```properties
   storePassword=<store password>
   keyPassword=<key password>
   keyAlias=yaxin
   storeFile=C:/Users/<you>/yaxin-release.jks
   ```

3. Build again; `android/app/build.gradle.kts` picks the key up automatically.
