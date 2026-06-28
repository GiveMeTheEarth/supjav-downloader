import requests
import re
import subprocess
import os
import asyncio
import aiohttp
import aiofiles
import shutil

class Downloader:
    def __init__(self):
        self.MIN_TS_SIZE = 1 * 1024

        self.verify = False
        if not self.verify:
            from urllib3.exceptions import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def __check_folder_exsist(self, path):
        if not path or path.strip() == "":
            raise ValueError("The output path is empty or invalid.")
        if not os.path.exists(path):
            os.makedirs(path)
            print(f'MADE: {path}')

    async def download_segment(self, session: aiohttp.ClientSession, sem, url, file_path):
        """ 1つの動画セグメントをダウンロードする（リトライ機能付き） """
        retry_count = 0
        max_retries = 5  

        while retry_count < max_retries:
            try:
                async with sem:
                    async with session.get(url, timeout=10, ssl=self.verify) as r:
                        r.raise_for_status()
                        async with aiofiles.open(file_path, "wb") as f:
                            async for chunk in r.content.iter_chunked(8192):
                                await f.write(chunk)
                                # print(f"✅ Downloaded: {file_path}")
                return file_path  # 成功時はファイル名を返す

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                retry_count += 1
                wait_time = 5
                print(f"⚠️ {url} failed: {type(e).__name__}: {e}", flush=True)
                print(f"🔄 Retrying... ({retry_count}/{max_retries}) Sleep for {wait_time} seconds.", end='\r', flush=True)
                await asyncio.sleep(wait_time)

        # print(f"❌ Failed to download after {max_retries} retries: {url}", end='\r', flush=True)

        raise RuntimeError(f"Download failed: {url} DO ONE MORE TIME.")

    async def download_video(self, urls, download_folder, filename):
        """ 並列処理で動画セグメントをダウンロード（進捗を上書き表示） """
        self.__check_folder_exsist(download_folder)
        downloaded_files = set()
        total_segments = len(urls)
        completed_segments = 0
        download_failed = 0

        print('#' * 60)
        sem = asyncio.Semaphore(20)

        connector = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=10
        )

        timeout = aiohttp.ClientTimeout(
            total=None,
            sock_connect=10,
            sock_read=30
        )

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            
            tasks = []

            for idx, url in enumerate(urls):
                file_path = os.path.join(download_folder, f"{idx:06d}.ts")
                if os.path.exists(file_path):
                    if os.path.getsize(file_path) > self.MIN_TS_SIZE:
                        downloaded_files.add(file_path)
                        completed_segments += 1
                        progress = (completed_segments / total_segments) * 100
                        print(f"Download Progress: {progress:.2f}% ({completed_segments}/{total_segments})", end='\r', flush=True)
                        continue
                    else:
                        os.remove(file_path)
                tasks.append(
                    asyncio.create_task(
                        self.download_segment(session, sem, url, file_path)
                    )
                )

            try:
                for task in asyncio.as_completed(tasks):
                    result = await task  # ここで RuntimeError が上がる
                    if result is None:
                        download_failed += 1
                        continue
                    downloaded_files.add(result)
                    completed_segments += 1

                    progress = (completed_segments / total_segments) * 100
                    if completed_segments == total_segments:
                        print(f"Download Progress: {progress:.2f}% ({completed_segments}/{total_segments})")
                        print('Download Completed.')
                    else:
                        print(f"Download Progress: {progress:.2f}% ({completed_segments}/{total_segments})", end='\r', flush=True)

            finally:
                # 念のため残タスクを完全回収
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        print('#' * 60)
        print()  # 最終進捗表示のあと改行
        print(f"Download Failed Count: {download_failed}")
        return downloaded_files
    
    def check_fake_extension(self, downloaded_files):
        is_jpeg_fake_video = any(f.endswith('.jpeg') for f in downloaded_files)

        return is_jpeg_fake_video
    
    def change_extension(self, downloaded_files):
        renamed_files = []
        for file in downloaded_files:
            base, ext = os.path.splitext(file)
            if ext.lower() == '.jpeg':
                new_file = base + '.ts'
                os.rename(file, new_file)
                renamed_files.append(new_file)
            else:
                renamed_files.append(file)

        return renamed_files

    def get_video(self, urls, output_folder, filename):
        safe_filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        temp_folder = os.path.join('./temp_download', safe_filename)
        """ ダウンロードした動画セグメントを結合してmp4にする """

        # check a folder that stores videos
        self.__check_folder_exsist(output_folder)

        # 2. 出力ファイル名を決定
        output_file = os.path.join(output_folder, f"{filename}.mp4")

        # 同じファイル名のmp4がすでにあるなら、ダウンロード前に止める
        if os.path.exists(output_file):
            raise FileExistsError(f"Output file already exists: {output_file}")

        # 1. ダウンロードする（並列処理）
        downloaded_files = asyncio.run(self.download_video(urls, temp_folder, filename))
        
        if not downloaded_files:
            print("No files downloaded. Exiting...")
            return

        # if downloaded files' extensions are jpeg, change it to ts.
        if self.check_fake_extension(downloaded_files):
            downloaded_files = self.change_extension(downloaded_files)
        
        # 3. ffmpegのリストファイルを作成
        list_file = f"{temp_folder}/temp_file_list.txt"
        sorted_files = sorted(downloaded_files, key=lambda x: int(re.search(r'(\d+)\.ts$', x).group(1)))

        with open(list_file, 'w', encoding="utf-8") as f:
            for file in sorted_files:
                f.write(f"file '{os.path.abspath(file)}'\n")
        
        # 4. ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-fflags", "+genpts",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-avoid_negative_ts", "make_zero",
            "-ignore_unknown",
            output_file,
        ]
        
        # print("Running FFmpeg with the following command:")
        # print(" ".join(cmd))
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

        for line in process.stderr:
            line = line.strip()
            if 'time=' in line:
                match = re.search(r'time=(\d{2}:\d{2}:\d{2}\.\d{2})', line)
                if match:
                    progress_time = match.group(1)
                    print(f"FFmpeg Progress: {progress_time}", end='\r', flush=True)
        
        process.wait()

        # FFmpeg の終了コード確認
        if process.returncode == 0:
            try:
                shutil.rmtree(temp_folder)
                print(f"Temporary folder removed: {temp_folder}")
            except Exception as e:
                print(f"Failed to remove temp folder {temp_folder}: {e}")
        else:
            print(f"FFmpeg failed with return code {process.returncode}. Keeping temporary files for resume.")

        print("✅ Ready to watch the video.")