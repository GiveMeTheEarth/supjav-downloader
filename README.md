# Supjav Downloader

A small Python downloader for Supjav pages. It opens the target page, extracts the HLS playlist, downloads the media segments in parallel, and merges them into an MP4 file with FFmpeg.

Use this only for content you are allowed to access and download.

## Features

- Loads Supjav pages with SeleniumBase undetected Chrome mode.
- Extracts the best available HLS stream from the page.
- Downloads segments concurrently.
- Retries failed segment downloads up to 5 times, including timeout errors such as `TimeoutError`.
- Supports resume from `temp_download/<title>/` when temporary files are left behind.
- Merges downloaded segments into a single `.mp4` with FFmpeg.

## Requirements

- Python 3.10 or newer
- Google Chrome
- FFmpeg available on `PATH`
- Python packages:
  - `requests`
  - `beautifulsoup4`
  - `selenium`
  - `seleniumbase`
  - `webdriver-manager`
  - `demjson3`
  - `aiohttp`
  - `aiofiles`

Install the Python dependencies:

```powershell
pip install requests beautifulsoup4 selenium seleniumbase webdriver-manager demjson3 aiohttp aiofiles
```

Check FFmpeg:

```powershell
ffmpeg -version
```

If PowerShell cannot find `ffmpeg`, install FFmpeg and add its `bin` directory to your `PATH`.

## Usage

Edit `example.py` and set:

- the Supjav page URL
- the output directory

Example:

```python
from supjav import supjav


class Example:
    def __init__(self):
        self.supjav = supjav()

    def run(self, url, path):
        self.supjav.run(url, path)


if __name__ == '__main__':
    app = Example()
    app.run('https://supjav.com/ja/398834.html', r'D:\DaikiVideos\supjav')
```

Run it:

```powershell
python example.py
```

The final MP4 is written to the output directory using the page title as the filename.

## How It Works

1. `supjav.py` opens the Supjav page and reads the page HTML.
2. It finds the active video server iframe.
3. It extracts the master HLS playlist URL.
4. It selects the highest-resolution variant playlist.
5. `SegmentsDownload.py` downloads each media segment into `temp_download/<safe_title>/`.
6. FFmpeg merges the segment list into `<output>/<title>.mp4`.
7. On successful merge, the temporary folder is deleted.

## Resume Behavior

Temporary segment files are stored under:

```text
temp_download/<video_title>/
```

If the download or FFmpeg merge fails, the temporary files are kept. Running the same download again will reuse existing segment files larger than the minimum size threshold and continue from the missing or incomplete files.

During segment download, transient network failures are retried automatically. For example, a timeout like this does not immediately stop the whole job:

```text
https://p16-ad-sg.ibyteimg.com/obj/ad-site-i18n/... failed: TimeoutError
Retrying... (1/5)
```

Each segment is retried up to 5 times before the downloader raises an error.

If you want a clean retry, delete the matching folder under `temp_download/`.

## Common Issues

### Output file already exists

The downloader stops before downloading if the target MP4 already exists:

```text
FileExistsError: Output file already exists
```

Rename or remove the existing output file before running again.

### FFmpeg failed with a non-zero return code

The temporary files are kept so you can inspect or resume the job.

Useful checks:

```powershell
ffprobe "temp_download/<video_title>/000000.ts"
```

```powershell
ffmpeg -y -fflags +genpts -f concat -safe 0 -i "temp_download/<video_title>/temp_file_list.txt" -map 0:v:0 -map 0:a:0? -c copy -bsf:a aac_adtstoasc -avoid_negative_ts make_zero -ignore_unknown "manual_check.mp4"
```

If the segment is actually a PNG/image stream instead of MPEG-TS, `-c copy` may not produce a normal MP4. In that case, encode the image sequence:

```powershell
ffmpeg -y -framerate 25 -f image2 -i "temp_download/<video_title>/%06d.ts" -c:v libx264 -pix_fmt yuv420p "manual_image_sequence.mp4"
```

### Browser or CAPTCHA problems

This project uses SeleniumBase with undetected Chrome mode. If page loading fails:

- make sure Chrome is installed and up to date
- try running again
- check whether the page requires manual CAPTCHA handling
- verify the Supjav page URL in a normal browser

### No video URLs found

The site layout or player script may have changed, or the selected server may not expose an HLS playlist in the expected format. Check the page manually and confirm that the video plays in the browser.

## Project Files

- `example.py` - minimal runnable example
- `supjav.py` - page loading, iframe parsing, playlist extraction
- `SegmentsDownload.py` - segment download, resume logic, FFmpeg merge
- `temp_download/` - temporary segment storage, created at runtime

## Notes

- The downloader currently has no command-line interface; use `example.py` or import `supjav` from your own script.
- Segment downloads use concurrent requests, so unstable networks may leave partial temporary files.
- FFmpeg errors are not fully printed by the script; use the manual commands above when investigating merge failures.
