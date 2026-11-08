import 'package:speech_to_text/speech_to_text.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// Encapsulates Azerbaijani (az-AZ) Speech-to-Text and Text-to-Speech on Android/iOS (Section 10).
class SpeechEngineService {
  final SpeechToText _stt = SpeechToText();
  final FlutterTts _tts = FlutterTts();
  bool _sttInitialized = false;

  Future<bool> initSpeech() async {
    try {
      _sttInitialized = await _stt.initialize();
      await _tts.setLanguage('az-AZ');
      await _tts.setSpeechRate(1.0);
      return _sttInitialized;
    } catch (_) {
      return false;
    }
  }

  Future<void> startListening({
    required void Function(String recognizedText) onResult,
  }) async {
    if (!_sttInitialized) {
      final ok = await initSpeech();
      if (!ok) return;
    }
    await _stt.listen(
      localeId: 'az_AZ',
      onResult: (result) {
        onResult(result.recognizedWords);
      },
    );
  }

  Future<void> stopListening() async {
    await _stt.stop();
  }

  Future<void> speak(String text, {double rate = 1.0}) async {
    try {
      await _tts.setLanguage('az-AZ');
      await _tts.setSpeechRate(rate);
      await _tts.speak(text);
    } catch (_) {
      // Fallback to text display if Azerbaijani TTS voice is unavailable on device (Section 10.3)
    }
  }
}

