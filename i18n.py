"""English / Russian interface texts (Task 5b).

HOW TO ADD A TEXT (Tasks 6, 7 and later): add ONE line with the same key to BOTH
dictionaries below (STRINGS["en"] and STRINGS["ru"]) and use t("your.key", name=value)
in the code. tests/test_i18n.py fails if a key is missing in one language, if the
{placeholders} differ between the languages, or if gui.py / video_processor.py use a
key that does not exist.

Rules for keys: dotted lowercase names, first part = area (btn, label, col, status, video,
dlg, ft, err, progress, info, app, lang, ffmpeg). Parameters use str.format placeholders
such as {name}. Times stay HH:MM:SS.mmm in both languages (pass them as parameters).
Product and tool names (Video Segment Editor, FFmpeg, VLC, MP4/MOV/AVI/MKV) stay in English.

Special parameter: kept_dir=<folder>. When given, t() appends the "Temporary files were
kept in: <folder>" sentence (key err.kept) to the text.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

LANGS = ("en", "ru")
DEFAULT_LANG = "en"
SETTINGS_KEY = "language"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # ---- window / header
        "app.name": "Video Segment Editor",
        "app.title": "Video Segment Editor",
        "lang.button": "RU",
        "info.none": "No video loaded.",
        "info.loaded": "{name} - {duration} - {width}x{height}",
        "btn.load_video": "Load Video",
        # ---- video area
        "video.vlc_missing": ("VLC is not installed, so the video preview is switched off.\n"
                              "You can still type start and end times by hand and create the video.\n"
                              "VLC is free. Download it here:"),
        "video.preview_failed": ("The preview could not start for this file.\n"
                                 "You can still type start and end times by hand."),
        # ---- transport / marking
        "label.volume": "Volume",
        "btn.mark_start": "Mark Start\nSet start point",
        "btn.mark_end": "Mark End\nSet end point",
        # ---- segment table
        "label.selected_segments": "Selected Segments",
        "col.n": "#",
        "col.start": "Start",
        "col.end": "End",
        "col.duration": "Duration",
        "label.total": "Total selected: {time}",
        "btn.up": "Move Up",
        "btn.down": "Move Down",
        "btn.edit": "Edit",
        "btn.delete": "Delete",
        "btn.clear": "Clear All",
        # ---- bottom area
        "btn.create": "Create Video",
        "status.load_to_begin": "Load a video to begin.",
        "status.reading": "Reading {name} ...",
        "status.loaded": "Video loaded.",
        "status.ffmpeg_missing": "FFmpeg is not installed.",
        # ---- dialogs
        "dlg.choose_video": "Choose a video",
        "dlg.cannot_open": "Cannot open this file",
        "dlg.ffmpeg_missing": "FFmpeg is missing",
        "ft.video": "Video files",
        "ft.all": "All files",
        "ffmpeg.help": ("FFmpeg was not found on this computer. It is needed to read and cut videos.\n\n"
                        "To install it:\n"
                        "1. Press the Windows key, type cmd and press Enter. A window called "
                        "Command Prompt opens.\n"
                        "2. Type this line and press Enter:\n\n"
                        "    winget install Gyan.FFmpeg\n\n"
                        "3. When it has finished, close this program and open it again."),
        # ---- errors raised by video_processor (str(exc) shows these English texts)
        "err.not_a_video": "This file could not be read as a video.",
        "err.probe_timeout": ("Reading this video took too long, so it was stopped. "
                              "Please try again or choose a different file."),
        "err.ffprobe_start": "FFprobe could not be started. Please check the FFmpeg installation.",
        "err.out_missing": "The finished video was not created.",
        "err.out_empty": "The finished video is empty.",
        "err.out_no_picture": "The finished video has no picture.",
        "err.out_no_sound": "The finished video has lost its sound. Try again. If it happens again, try a different video file.",
        "err.out_audio_count": ("Audio tracks in the finished video: {actual}, expected: "
                                "{expected}."),
        "err.out_length_unreadable": "The length of the finished video could not be read.",
        "err.out_wrong_length": ("The finished video has the wrong length ({actual} s instead of "
                                 "{expected} s). Try again. If it happens again, try a different video file."),
        "err.out_av_mismatch": ("The picture and the sound of the finished video have different "
                                "lengths ({video} s of picture, {audio} s of sound). The source "
                                "file may be damaged."),
        "err.out_frames_wrong": ("Frames in the finished video: {actual}, expected about "
                                 "{expected}. Part of the picture may be missing."),
        "err.out_start_offset": ("The picture of the finished video starts {offset} s late, "
                                 "so it would not match the sound."),
        "err.disk_check": ("The free space on the drive of the folder could not be checked. Please make "
                           "sure the folder exists and that you can open it."),
        "err.disk_low": ("There is not enough free space on drive {drive}. About {needed} MB is "
                         "needed but only {free} MB is free. Free up some space on that drive "
                         "and try again."),
        "err.folder_readonly": ("Cannot save in this folder: it is read-only or not allowed. "
                                "Choose a video in a folder you can write to."),
        "err.empty_list": "Please add at least one segment first.",
        "err.source_unopenable": ("The video file could not be opened. Please check that "
                                  "it still exists."),
        "err.ffmpeg_failed": ("FFmpeg could not process this video. "
                            "Try again. If it happens again, try a different video file."),
        "err.source_locked": ("The video file is in use by another program or access is "
                              "denied. Close the other program and try again."),
        "err.source_missing": ("The original video file was not found any more. Was it moved "
                               "or deleted?"),
        "err.windows_denied": ("Windows did not allow writing there. Please check that the "
                               "folder is not read-only."),
        "err.disk_full": "The disk is full. Free up some space and try again.",
        "err.file_problem": "A file problem stopped the work. Try again. If it happens again, try a different video file.",
        "err.save_denied": ("The finished video could not be saved: Windows did not allow "
                            "writing there."),
        "err.save_disk_full": "The disk is full, so the finished video could not be saved.",
        "err.save_failed": "The finished video could not be saved.",
        "err.part_invalid": ("Segment {i} of {n} could not be cut correctly: the result is "
                             "empty or has the wrong length. The video file may be damaged, or "
                             "its length information may be wrong. Try again. If it happens again, try a different video file."),
        "err.segment_empty": ("Segment {i} produced no video. Its times may be past the "
                              "end of the file."),
        "err.cancelled": "Cancelled.",
        "err.kept": ("Temporary files were kept in: {path}\n"
                     "They are deleted automatically after 7 days."),
        # ---- segment list and time errors (segment_manager; str(exc) shows these English texts)
        "err.time_empty": ("Please type a time. "
                           "Use hours:minutes:seconds, for example 00:01:05.250. Short forms: 1:05 = 1 minute 5 seconds, 65 = 65 seconds."),
        "err.time_invalid": ("'{text}' is not a valid time. "
                             "Use hours:minutes:seconds, for example 00:01:05.250. Short forms: 1:05 = 1 minute 5 seconds, 65 = 65 seconds."),
        "err.time_seconds": "Seconds must be below 60 in '{text}'.",
        "err.time_minutes": "Minutes must be below 60 in '{text}'.",
        "err.time_negative": "Time cannot be negative.",
        "err.seg_start_negative": "The start time cannot be before the beginning of the video.",
        "err.seg_end_not_after": "The end time must be after the start time.",
        "err.seg_past_end": "The end time is past the end of the video ({duration}).",
        "err.seg_start_late": "The start time must be before the end of the video ({duration}).",
        "err.seg_max": "You can have at most {max} segments. Delete one to add another.",
        "err.seg_bad_index": "That segment is not in the list.",
        "err.no_start": "Press Mark Start first, then Mark End.",
        # ---- marking, table, dialogs (Task 6)
        "btn.mark_start_set": "Mark Start\n{time}",
        "mark.hint": "Move to where the segment should begin, then press Mark Start.",
        "mark.pending": "Start marked at {time}. Move to the end point and press Mark End.",
        "mark.added": "Segment {n} added: {start} - {end}",
        "mark.manual_hint": ("No video preview: type the start and end times and press Add segment. "
                             "Use hours:minutes:seconds, for example 00:01:05.250. Short forms: 1:05 = 1 minute 5 seconds, 65 = 65 seconds."),
        "btn.add_segment": "Add segment",
        "btn.ok": "OK",
        "btn.cancel": "Cancel",
        "dlg.max_segments": "Segment limit reached",
        "dlg.edit_title": "Edit segment {n}",
        "dlg.edit_hint": "Use hours:minutes:seconds, for example 00:01:05.250. Short forms: 1:05 = 1 minute 5 seconds, 65 = 65 seconds.",
        "dlg.clear_title": "Clear all segments",
        "dlg.clear_message": "Remove all {n} segments from the list?",
        "dlg.clear_message_one": "Remove the segment from the list?",
        "dlg.new_video_title": "Replace the video?",
        "dlg.new_video_message": ("Loading {name} clears your segment list "
                                  "(segments in the list: {n}). Continue?"),
        "status.segment_deleted": "Segment {n} deleted.",
        "status.segment_edited": "Segment {n} updated.",
        "status.cleared": "All segments removed.",
        # ---- Create Video flow
        "dlg.create_title": "Create Video",
        "dlg.create_confirm": ("Segments: {n}\nTotal length: {total}\nOutput file: {name}\n"
                               "Folder: {folder}\n\n{notes}"
                               "Your original video will not be changed. Create the video?"),
        "dlg.create_notes": "What will change in the new video:\n{list}",
        "note.hdr_to_sdr": "HDR video will be converted to normal video; colours may look slightly different",
        "note.color_format": "colour format changed to a standard 8-bit one; colours may differ very slightly",
        "note.deinterlace": "interlaced picture made progressive; fine detail in fast motion may look slightly different",
        "note.odd_size": "odd picture size cropped by 1 pixel; one row or column of pixels at the edge is lost",
        "note.audio_tracks": "all {n} audio tracks are kept; nothing is lost",
        "note.subtitles_dropped": "{n} subtitle track(s) not kept; the new video has no subtitles",
        "note.chapters_dropped": "chapters not kept; the new video has no chapter marks",
        "dlg.create_failed_title": "The video was not created",
        "dlg.create_done_title": "Video created",
        "dlg.close_title": "Stop and close?",
        "dlg.close_message": "A video is being created. Stop and close?",
        "btn.cancel_job": "Cancel",
        "btn.open_folder": "Open folder",
        "dlg.cancel_job_title": "Stop creating the video?",
        "dlg.cancel_job_message": "Stop creating the video? Temporary files are kept and deleted automatically after 7 days.",
        "status.stopping": "Stopping... please wait.",
        "status.creating": "Creating the video. Please wait...",
        "status.done": "Done.",
        "out.saved": "Saved to: {path}",
        # ---- WP3: hints, tooltips, themed dialogs
        "tip.play": "Play",
        "tip.pause": "Pause",
        "tip.stop": "Stop",
        "table.empty": "Marked segments appear here.",
        "mark.limit": "Limit of {max} segments reached. Delete one to add another.",
        "btn.yes": "Yes",
        "btn.no": "No",
        "btn.create_video": "Create Video",
        # ---- progress messages (VideoJob)
        "progress.cut": "Cutting segment {i} of {n}",
        "progress.cut_done": "Segment {i} of {n} cut",
        "progress.join": "Joining the segments",
        "progress.verify": "Checking the finished video",
        "progress.done": "Done",
    },
    "ru": {
        # ---- window / header
        "app.name": "Video Segment Editor",
        "app.title": "Video Segment Editor — редактор видеофрагментов",
        "lang.button": "EN",
        "info.none": "Видео не загружено.",
        "info.loaded": "{name} - {duration} - {width}x{height}",
        "btn.load_video": "Загрузить видео",
        # ---- video area
        "video.vlc_missing": ("Проигрыватель VLC не установлен, поэтому предпросмотр видео отключён.\n"
                              "Вы всё равно можете ввести время начала и конца вручную и создать видео.\n"
                              "VLC бесплатный. Скачать его можно здесь:"),
        "video.preview_failed": ("Не удалось запустить предпросмотр для этого файла.\n"
                                 "Время начала и конца по-прежнему можно ввести вручную."),
        # ---- transport / marking
        "label.volume": "Громкость",
        "btn.mark_start": "Отметить начало\nЗадать точку начала",
        "btn.mark_end": "Отметить конец\nЗадать точку конца",
        # ---- segment table
        "label.selected_segments": "Выбранные фрагменты",
        "col.n": "№",
        "col.start": "Начало",
        "col.end": "Конец",
        "col.duration": "Длительность",
        "label.total": "Всего выбрано: {time}",
        "btn.up": "Вверх",
        "btn.down": "Вниз",
        "btn.edit": "Изменить",
        "btn.delete": "Удалить",
        "btn.clear": "Очистить список",
        # ---- bottom area
        "btn.create": "Создать видео",
        "status.load_to_begin": "Чтобы начать, загрузите видео.",
        "status.reading": "Чтение файла {name}...",
        "status.loaded": "Видео загружено.",
        "status.ffmpeg_missing": "FFmpeg не установлен.",
        # ---- dialogs
        "dlg.choose_video": "Выберите видео",
        "dlg.cannot_open": "Не удаётся открыть файл",
        "dlg.ffmpeg_missing": "Не найден FFmpeg",
        "ft.video": "Видеофайлы",
        "ft.all": "Все файлы",
        "ffmpeg.help": ("FFmpeg не найден на этом компьютере. Он нужен, чтобы читать и нарезать видео.\n\n"
                        "Чтобы установить его:\n"
                        "1. Нажмите клавишу Windows, введите cmd и нажмите Enter. Откроется окно "
                        "«Командная строка» (Command Prompt).\n"
                        "2. Введите эту строку и нажмите Enter:\n\n"
                        "    winget install Gyan.FFmpeg\n\n"
                        "3. Когда установка закончится, закройте программу и откройте её снова."),
        # ---- errors raised by video_processor
        "err.not_a_video": "Не удалось прочитать этот файл как видео.",
        "err.probe_timeout": ("Чтение видео заняло слишком много времени и было остановлено. "
                              "Попробуйте ещё раз или выберите другой файл."),
        "err.ffprobe_start": "Не удалось запустить FFprobe. Проверьте установку FFmpeg.",
        "err.out_missing": "Готовое видео не было создано.",
        "err.out_empty": "Готовое видео оказалось пустым.",
        "err.out_no_picture": "В готовом видео нет изображения.",
        "err.out_no_sound": "В готовом видео пропал звук. Попробуйте ещё раз. Если ошибка повторится, попробуйте другой видеофайл.",
        "err.out_audio_count": ("Число звуковых дорожек в готовом видео: {actual}, "
                                "ожидалось: {expected}."),
        "err.out_length_unreadable": "Не удалось определить длительность готового видео.",
        "err.out_wrong_length": ("Длительность готового видео не совпадает с ожидаемой: {actual} с "
                                 "вместо {expected} с. Попробуйте ещё раз. Если ошибка повторится, попробуйте другой видеофайл."),
        "err.out_av_mismatch": ("Изображение и звук в готовом видео имеют разную длительность "
                                "(изображение {video} с, звук {audio} с). Возможно, исходный "
                                "файл повреждён."),
        "err.out_frames_wrong": ("Число кадров в готовом видео: {actual}, ожидалось примерно "
                                 "{expected}. Часть изображения могла пропасть."),
        "err.out_start_offset": ("Изображение в готовом видео начинается с задержкой {offset} с, "
                                 "поэтому оно не совпало бы со звуком."),
        "err.disk_check": ("Не удалось проверить свободное место на диске, где находится папка. "
                           "Убедитесь, что папка существует и что у вас есть к ней доступ."),
        "err.disk_low": ("Недостаточно свободного места на диске {drive}. Нужно примерно {needed} МБ, "
                         "а свободно только {free} МБ. Освободите место на этом диске и "
                         "попробуйте снова."),
        "err.folder_readonly": ("В эту папку нельзя сохранить файл: она доступна только для чтения "
                                "или запись в неё запрещена. Выберите видео из папки, в которую "
                                "можно сохранять файлы."),
        "err.empty_list": "Сначала добавьте хотя бы один фрагмент.",
        "err.source_unopenable": ("Не удалось открыть видеофайл. Проверьте, что он ещё "
                                  "существует."),
        "err.ffmpeg_failed": ("FFmpeg не смог обработать это видео. "
                            "Попробуйте ещё раз. Если ошибка повторится, попробуйте другой видеофайл."),
        "err.source_locked": ("Видеофайл занят другой программой или доступ к нему запрещён. "
                              "Закройте другую программу и попробуйте снова."),
        "err.source_missing": ("Исходный видеофайл больше не найден. Возможно, его "
                               "переместили или удалили?"),
        "err.windows_denied": ("Запись в эту папку запрещена Windows. Проверьте, что папка "
                               "не защищена от записи."),
        "err.disk_full": "Диск заполнен. Освободите место и попробуйте снова.",
        "err.file_problem": ("Работа остановлена из-за проблемы с файлом. "
                            "Попробуйте ещё раз. Если ошибка повторится, попробуйте другой видеофайл."),
        "err.save_denied": ("Не удалось сохранить готовое видео: запись в эту папку "
                            "запрещена Windows."),
        "err.save_disk_full": "Диск заполнен, поэтому готовое видео не удалось сохранить.",
        "err.save_failed": "Не удалось сохранить готовое видео.",
        "err.part_invalid": ("Фрагмент {i} из {n} вырезан неправильно: результат пустой или "
                             "имеет неверную длительность. Возможно, видеофайл повреждён или в "
                             "нём указана неверная длительность. Попробуйте ещё раз. Если ошибка повторится, попробуйте другой видеофайл."),
        "err.segment_empty": ("Фрагмент {i} получился пустым. Возможно, его время выходит "
                              "за конец видео."),
        "err.cancelled": "Отменено.",
        "err.kept": ("Временные файлы сохранены: {path}\n"
                     "Они удаляются автоматически через 7 дней."),
        # ---- segment list and time errors (segment_manager)
        "err.time_empty": ("Введите время. "
                           "Введите часы:минуты:секунды, например 00:01:05.250. Короткие формы: 1:05 = 1 минута 5 секунд, 65 = 65 секунд."),
        "err.time_invalid": ("«{text}» — неверное время. "
                             "Введите часы:минуты:секунды, например 00:01:05.250. Короткие формы: 1:05 = 1 минута 5 секунд, 65 = 65 секунд."),
        "err.time_seconds": "Секунд в «{text}» должно быть меньше 60.",
        "err.time_minutes": "Минут в «{text}» должно быть меньше 60.",
        "err.time_negative": "Время не может быть отрицательным.",
        "err.seg_start_negative": "Время начала не может быть раньше начала видео.",
        "err.seg_end_not_after": "Время конца должно быть позже времени начала.",
        "err.seg_past_end": "Время конца выходит за конец видео ({duration}).",
        "err.seg_start_late": "Время начала должно быть раньше конца видео ({duration}).",
        "err.seg_max": "В списке может быть не больше {max} фрагментов. Удалите один, чтобы добавить другой.",
        "err.seg_bad_index": "Такого фрагмента нет в списке.",
        "err.no_start": "Сначала нажмите «Отметить начало», затем «Отметить конец».",
        # ---- marking, table, dialogs (Task 6)
        "btn.mark_start_set": "Отметить начало\n{time}",
        "mark.hint": "Перейдите к месту начала фрагмента и нажмите «Отметить начало».",
        "mark.pending": ("Начало отмечено: {time}. Перейдите к месту окончания фрагмента и нажмите "
                         "«Отметить конец»."),
        "mark.added": "Фрагмент {n} добавлен: {start} - {end}",
        "mark.manual_hint": ("Предпросмотр недоступен: введите время начала и конца и нажмите "
                             "«Добавить фрагмент». Введите часы:минуты:секунды, например 00:01:05.250. Короткие формы: 1:05 = 1 минута 5 секунд, 65 = 65 секунд."),
        "btn.add_segment": "Добавить фрагмент",
        "btn.ok": "ОК",
        "btn.cancel": "Отмена",
        "dlg.max_segments": "Достигнут лимит фрагментов",
        "dlg.edit_title": "Изменение фрагмента {n}",
        "dlg.edit_hint": "Введите часы:минуты:секунды, например 00:01:05.250. Короткие формы: 1:05 = 1 минута 5 секунд, 65 = 65 секунд.",
        "dlg.clear_title": "Очистка списка",
        "dlg.clear_message": "Удалить все фрагменты ({n}) из списка?",
        "dlg.clear_message_one": "Удалить фрагмент из списка?",
        "dlg.new_video_title": "Заменить видео?",
        "dlg.new_video_message": ("При загрузке файла {name} список фрагментов будет очищен "
                                  "(фрагментов: {n}). Продолжить?"),
        "status.segment_deleted": "Фрагмент {n} удалён.",
        "status.segment_edited": "Фрагмент {n} изменён.",
        "status.cleared": "Все фрагменты удалены.",
        # ---- Create Video flow
        "dlg.create_title": "Создать видео",
        "dlg.create_confirm": ("Фрагментов: {n}\nОбщая длительность: {total}\n"
                               "Итоговый файл: {name}\nПапка: {folder}\n\n{notes}"
                               "Исходное видео не изменится. Создать видео?"),
        "dlg.create_notes": "Что изменится в новом видео:\n{list}",
        "note.hdr_to_sdr": "HDR-видео будет преобразовано в обычное; цвета могут немного отличаться",
        "note.color_format": "цветовой формат заменён на стандартный 8-битный; цвета могут очень слегка отличаться",
        "note.deinterlace": "чересстрочное изображение станет прогрессивным; мелкие детали при быстром движении могут выглядеть чуть иначе",
        "note.odd_size": "нечётный размер кадра обрезан на 1 пиксель; теряется один ряд или столбец пикселей у края",
        "note.audio_tracks": "все звуковые дорожки сохранены ({n}); ничего не теряется",
        "note.subtitles_dropped": "дорожки субтитров ({n}) не сохраняются; в новом видео не будет субтитров",
        "note.chapters_dropped": "главы не сохраняются; в новом видео не будет глав",
        "dlg.create_failed_title": "Видео не создано",
        "dlg.create_done_title": "Видео создано",
        "dlg.close_title": "Остановить и закрыть?",
        "dlg.close_message": "Идёт создание видео. Остановить и закрыть программу?",
        "btn.cancel_job": "Отмена",
        "btn.open_folder": "Открыть папку",
        "dlg.cancel_job_title": "Остановить создание видео?",
        "dlg.cancel_job_message": ("Остановить создание видео? Временные файлы будут "
                                   "сохранены и удалены автоматически через 7 дней."),
        "status.stopping": "Остановка... Пожалуйста, подождите.",
        "status.creating": "Идёт создание видео. Пожалуйста, подождите...",
        "status.done": "Готово.",
        "out.saved": "Файл сохранён: {path}",
        # ---- WP3: hints, tooltips, themed dialogs
        "tip.play": "Воспроизвести",
        "tip.pause": "Пауза",
        "tip.stop": "Остановить",
        "table.empty": "Здесь появятся отмеченные фрагменты.",
        "mark.limit": "Достигнут предел: {max} фрагментов. Удалите один, чтобы добавить другой.",
        "btn.yes": "Да",
        "btn.no": "Нет",
        "btn.create_video": "Создать видео",
        # ---- progress messages (VideoJob)
        "progress.cut": "Вырезается фрагмент {i} из {n}",
        "progress.cut_done": "Фрагмент {i} из {n} вырезан",
        "progress.join": "Фрагменты объединяются",
        "progress.verify": "Проверка готового видео",
        "progress.done": "Готово",
    },
}

_lang = DEFAULT_LANG
_DECIMAL = re.compile(r"^\d+\.\d+$")


def get_language() -> str:
    return _lang


def set_language(code: str) -> None:
    global _lang
    if code not in LANGS:
        raise ValueError(f"Unknown language: {code!r}")
    _lang = code


def t_lang(lang: str, key: str, **params) -> str:
    """Translate into a given language (falls back to English, then to the key)."""
    kept = params.pop("kept_dir", None)
    template = STRINGS.get(lang, {}).get(key)
    if template is None:
        template = STRINGS[DEFAULT_LANG].get(key, key)
    if lang == "ru":  # Russian writes decimals with a comma: "12.3" -> "12,3"
        params = {k: (v.replace(".", ",") if isinstance(v, str) and _DECIMAL.match(v) else v)
                  for k, v in params.items()}
    try:
        text = template.format(**params)
    except (KeyError, IndexError, ValueError) as exc:
        # never crash the interface, but leave a trace for the developer
        print(f"i18n: cannot fill {key!r} ({lang}) with {sorted(params)}: {exc!r}",
              file=sys.stderr)
        text = template
    if kept is not None:
        text = f"{text} {t_lang(lang, 'err.kept', path=kept)}"
    return text


def t(key: str, **params) -> str:
    """Text for `key` in the current language."""
    return t_lang(_lang, key, **params)


# --------------------------------------------------------------------- settings
def default_settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "VideoSegmentEditor" / "settings.json"


def _read_settings(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))  # a BOM is accepted
    except (OSError, ValueError):  # missing, unreadable, bad JSON or bad UTF-8
        return {}
    return data if isinstance(data, dict) else {}


def load_saved_language(settings_path: Path) -> str:
    """Saved language code, or "en" when the file is missing, corrupt or unknown."""
    code = _read_settings(settings_path).get(SETTINGS_KEY)
    return code if code in LANGS else DEFAULT_LANG


def save_language(settings_path: Path, code: str) -> None:
    """Write the language into settings.json (other keys kept). Never raises on I/O errors."""
    if code not in LANGS:
        raise ValueError(f"Unknown language: {code!r}")
    path = Path(settings_path)
    data = _read_settings(path)
    data[SETTINGS_KEY] = code
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        print(f"could not save settings to {path}: {exc!r}", file=sys.stderr)
        try:
            tmp.unlink()
        except OSError:
            pass
