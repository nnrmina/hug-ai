import 'dart:async';

import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_to_text.dart';

typedef SpeechResultCallback = void Function(String text, bool isFinal);

/// Azerbaijani speech-to-text and text-to-speech wrapper.
///
/// `SpeechToText` is a process-wide singleton, so listeners are re-attached
/// on every [startListening] call — whichever screen listens last owns them.
class SpeechEngineService {
  static const Duration _shortTimeout = Duration(seconds: 2);

  /// The service instance that started the current listen session.
  static SpeechEngineService? _activeOwner;

  final SpeechToText _stt = SpeechToText();
  final FlutterTts _tts = FlutterTts();

  bool _sttReady = false;
  bool _ttsReady = false;
  bool _isListening = false;
  bool _disposed = false;

  String? _localeId;
  String? _ttsLanguage;

  /// Visible note when Azerbaijani recognition is not available.
  String? localeNote;

  /// Called whenever the real listening state changes.
  void Function(bool isListening)? onListeningChanged;

  /// Called with a user-facing Azerbaijani message on recognition errors.
  void Function(String message)? onError;

  bool get isListening => _isListening;

  Future<bool> init() async {
    if (_sttReady) return true;
    try {
      _sttReady = await _stt.initialize(
        onStatus: _handleStatus,
        onError: _handleError,
      );
    } catch (_) {
      _sttReady = false;
    }
    if (_sttReady) await _pickLocale();
    return _sttReady;
  }

  Future<void> _pickLocale() async {
    try {
      final locales = await _stt.locales();
      String norm(String id) => id.replaceAll('-', '_').toLowerCase();
      final ids = locales.map((l) => l.localeId).toList();
      String? find(String prefix) {
        for (final id in ids) {
          if (norm(id) == prefix || norm(id).startsWith('${prefix}_')) {
            return id;
          }
        }
        return null;
      }

      if (ids.isEmpty) {
        // Some recognisers do not report locales; try Azerbaijani anyway.
        _localeId = 'az_AZ';
        localeNote = null;
        return;
      }
      final az = find('az_az') ?? find('az');
      if (az != null) {
        _localeId = az;
        localeNote = null;
        return;
      }
      final tr = find('tr_tr') ?? find('tr');
      if (tr != null) {
        _localeId = tr;
        localeNote =
            'Telefonda Azərbaycan dili üçün nitq tanıma tapılmadı. Türk dili istifadə olunur — tanınma dəqiq olmaya bilər.';
        return;
      }
      final system = await _stt.systemLocale();
      _localeId = system?.localeId;
      localeNote =
          'Telefonda Azərbaycan dili üçün nitq tanıma tapılmadı. Telefonun əsas dili istifadə olunur.';
    } catch (_) {
      _localeId = 'az_AZ';
    }
  }

  Future<void> _initTts() async {
    if (_ttsReady) return;
    try {
      await _tts.awaitSpeakCompletion(true).timeout(_shortTimeout);
      for (final lang in const ['az-AZ', 'tr-TR']) {
        final available =
            await _tts.isLanguageAvailable(lang).timeout(_shortTimeout);
        if (available == true || available == 1) {
          _ttsLanguage = lang;
          break;
        }
      }
      if (_ttsLanguage != null) {
        await _tts.setLanguage(_ttsLanguage!).timeout(_shortTimeout);
      }
      _ttsReady = true;
    } catch (_) {
      // TTS unavailable: text is always shown on screen as well.
      _ttsReady = true; // don't retry (and wait) on every utterance
    }
  }

  void _handleStatus(String status) {
    if (status == SpeechToText.listeningStatus) {
      _setListening(true);
    } else if (status == SpeechToText.notListeningStatus ||
        status == SpeechToText.doneStatus) {
      _setListening(false);
    }
  }

  void _handleError(SpeechRecognitionError error) {
    _setListening(false);
    final msg = error.errorMsg;
    String text;
    if (msg.contains('no_match') || msg.contains('speech_timeout')) {
      text = 'Sizi eşitmədim. Danışmaq üçün mikrofona toxunun.';
    } else if (msg.contains('permission')) {
      text = 'Mikrofon icazəsi yoxdur. Tənzimləmələrdən icazə verin.';
    } else if (msg.contains('network')) {
      text = 'İnternet bağlantısı yoxdur — nitq tanınmadı.';
    } else if (msg.contains('busy')) {
      text = 'Mikrofon məşğuldur. Bir az sonra yenidən cəhd edin.';
    } else {
      text = 'Nitq tanıma xətası. Yenidən cəhd edin.';
    }
    onError?.call(text);
  }

  void _setListening(bool value) {
    if (_disposed || _isListening == value) return;
    _isListening = value;
    onListeningChanged?.call(value);
  }

  /// Starts listening. Returns false if recognition is unavailable.
  Future<bool> startListening({required SpeechResultCallback onResult}) async {
    if (_disposed) return false;
    if (!await init()) return false;
    // Re-attach listeners (singleton may have been used by another screen).
    _stt.statusListener = _handleStatus;
    _stt.errorListener = _handleError;
    try {
      await _tts.stop().timeout(_shortTimeout, onTimeout: () => null);
      if (_stt.isListening) await _stt.cancel();
      await _stt.listen(
        onResult: (r) {
          if (_disposed) return;
          onResult(r.recognizedWords, r.finalResult);
        },
        listenOptions: SpeechListenOptions(
          localeId: _localeId,
          partialResults: true,
          cancelOnError: true,
          listenMode: ListenMode.confirmation,
          listenFor: const Duration(seconds: 30),
          pauseFor: const Duration(seconds: 4),
        ),
      );
      _activeOwner = this;
      _setListening(true);
      return true;
    } catch (_) {
      _setListening(false);
      return false;
    }
  }

  Future<void> stopListening() async {
    if (identical(_activeOwner, this)) {
      try {
        await _stt.stop();
      } catch (_) {}
    }
    _setListening(false);
  }

  Future<void> speak(String text, {double rate = 0.5}) async {
    if (_disposed || text.trim().isEmpty) return;
    await _initTts();
    if (_ttsLanguage == null) return; // no suitable voice; text is on screen
    try {
      await _tts.setSpeechRate(rate).timeout(_shortTimeout);
      // Never let a stuck TTS engine block the conversation.
      final maxDuration = Duration(
          milliseconds: (3000 + text.length * 120).clamp(3000, 30000).toInt());
      await _tts.speak(text).timeout(maxDuration, onTimeout: () => null);
    } catch (_) {}
  }

  Future<void> stopSpeaking() async {
    try {
      await _tts.stop().timeout(_shortTimeout, onTimeout: () => null);
    } catch (_) {}
  }

  /// Stops the mic and TTS. Call from the owning widget's dispose().
  void dispose() {
    if (_disposed) return;
    onListeningChanged = null;
    onError = null;
    _isListening = false;
    _disposed = true;
    if (identical(_activeOwner, this)) {
      _activeOwner = null;
      try {
        _stt.cancel();
      } catch (_) {}
    }
    try {
      _tts.stop();
    } catch (_) {}
  }
}
