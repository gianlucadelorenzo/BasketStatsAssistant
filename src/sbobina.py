#!/usr/bin/env python3
import sys
import logging
import argparse
from pathlib import Path
from faster_whisper import WhisperModel


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
   parser = argparse.ArgumentParser(description="Transcribe all .m4a files in a folder and save .txt outputs.")
   parser.add_argument("audio_dir", nargs="?", default="/basket_stats_assistant/data", help="Path to folder containing .m4a files")
   parser.add_argument("--model-size", default="medium", help="Model size for WhisperModel (tiny, base, medium, large)")
   parser.add_argument("--device", default="cpu", help="Device to run model on (cpu or cuda)")
   parser.add_argument("--language", default="it", help="Language code for transcription (default: it)")
   args = parser.parse_args()

   audio_dir = Path(args.audio_dir)
   if not audio_dir.exists() or not audio_dir.is_dir():
      logging.error(f"Audio directory does not exist or is not a directory: {audio_dir}")
      sys.exit(1)

   m4a_files = sorted(audio_dir.glob("*.m4a"))
   if not m4a_files:
      logging.warning(f"No .m4a files found in {audio_dir}")
      return

   logging.info(f"Initializing Whisper model (size={args.model_size}, device={args.device})")
   model = WhisperModel(args.model_size, device=args.device, compute_type="int8")

   for audio_path in m4a_files:
      logging.info(f"Transcribing file: {audio_path}")
      try:
         segments, info = model.transcribe(str(audio_path), beam_size=5, language=args.language)
      except Exception as e:
         logging.error(f"Transcription failed for {audio_path}: {e}")
         continue

      transcription_lines = []
      for segment in segments:
         minuti_inizio = int(segment.start // 60)
         secondi_inizio = int(segment.start % 60)
         transcription_lines.append(f"{segment.text.strip()}")

      transcription = "\n".join(transcription_lines)
      out_path = audio_path.with_suffix('.txt')
      try:
         out_path.write_text(transcription, encoding='utf-8')
         logging.info(f"Wrote transcription to {out_path}")
      except Exception as e:
         logging.error(f"Failed to write transcription for {audio_path}: {e}")


if __name__ == '__main__':
   main()






