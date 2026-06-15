# TenderRadarLite Windows Quick Start

## 閫傜敤浜虹兢

鏈鏄庨€傜敤浜庡笇鏈涘湪 Windows 鏈湴杩愯 TenderRadarLite 骞剁敓鎴?HTML 鎶ュ憡鐨勭敤鎴枫€?
鏈湴 HTML 鎶ュ憡妯″紡涓嶄緷璧栭涔︼紝涓嶉渶瑕?App Secret锛屼笉闇€瑕?Webhook锛屼篃涓嶉渶瑕?`chat_id`銆?椋炰功灞炰簬楂樼骇鍙€夊姛鑳斤紝涓嶆槸 Windows 鏈湴鎶ュ憡鐨勫繀闇€椤广€?
## 绗竴娆′娇鐢ㄥ墠

1. 瀹夎 Python 3.11 鎴栨洿楂樼増鏈紝骞剁‘璁?`python` 鍛戒护鍙敤銆?2. 杩涘叆椤圭洰鏍圭洰褰?`D:\TenderRadarLite`銆?3. 鍙€夊垱寤鸿櫄鎷熺幆澧冿細

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

4. 瀹夎渚濊禆锛?
```powershell
python -m pip install -r requirements.txt
```

## 鎺ㄨ崘浣跨敤娴佺▼

1. 鍙屽嚮 `scripts\妫€鏌ヨ繍琛岀幆澧?bat`
2. 鍙屽嚮 `scripts\鍚姩鏈湴鎷涙姇鏍囨姤鍛?bat`
3. 鎵撳紑 `reports\latest.html` 鏌ョ湅鏈€鏂版湰鍦版姤鍛?
## 甯哥敤鑴氭湰璇存槑

### `scripts\鍚姩鏈湴鎷涙姇鏍囨姤鍛?bat`

- 鎵ц `python run_mvp.py --local-html`
- 鐢熸垚鏈湴 HTML 鎶ュ憡 `reports\latest.html`
- 鎴愬姛鍚庣敱 Python 鍐呴儴鑷姩灏濊瘯鎵撳紑娴忚鍣?- 澶辫触鏃剁獥鍙ｄ細鍋滅暀锛屾柟渚挎煡鐪嬮敊璇?
### `scripts\鎵撳紑鏈€鏂版姤鍛?bat`

- 鐩存帴鎵撳紑 `reports\latest.html`
- 涓嶈繍琛屾姄鍙?- 濡傛灉鎶ュ憡涓嶅瓨鍦紝浼氭彁绀哄厛杩愯 `鍚姩鏈湴鎷涙姇鏍囨姤鍛?bat`

### `scripts\鏌ョ湅杩愯鏃ュ織.bat`

- 鎵撳紑 `logs\` 鐩綍
- 鏂逛究鏌ョ湅鏈湴杩愯鏃ュ織
- 涓嶈繍琛屾姄鍙栵紝涓嶈Е鍙戦涔?
### `scripts\妫€鏌ヨ繍琛岀幆澧?bat`

- 妫€鏌ュ綋鍓嶇洰褰曟槸鍚︽纭?- 妫€鏌?Python 鏄惁鍙敤鍙婄増鏈?- 妫€鏌?`requirements.txt`銆乣run_mvp.py`銆乣data/`銆乣logs/`銆乣reports/`
- 妫€鏌ュ叧閿緷璧栨槸鍚﹀彲瀵煎叆
- 涓嶈嚜鍔ㄥ畨瑁呬緷璧栵紝涓嶈嚜鍔ㄥ垱寤鸿櫄鎷熺幆澧?
## 甯歌闂

### 鍙屽嚮闂€€鎬庝箞鍔?
鍏堝弻鍑?`scripts\妫€鏌ヨ繍琛岀幆澧?bat`銆傝鑴氭湰浼氬仠鐣欑獥鍙ｏ紝骞舵彁绀虹己灏?Python銆佷緷璧栨垨鐩綍鐨勯棶棰樸€?
### Python 鏈畨瑁呮€庝箞鍔?
鍏堝畨瑁?Python 3.11 鎴栨洿楂樼増鏈紝骞剁‘璁ゅ湪鍛戒护琛屼腑鎵ц `python --version` 鑳界湅鍒扮増鏈彿銆?
### 渚濊禆缂哄け鎬庝箞鍔?
鍦ㄩ」鐩牴鐩綍鎵ц锛?
```powershell
python -m pip install -r requirements.txt
```

### 娌℃湁鐢熸垚鎶ュ憡鎬庝箞鍔?
鍏堟煡鐪?`scripts\鍚姩鏈湴鎷涙姇鏍囨姤鍛?bat` 绐楀彛涓殑閿欒鎻愮ず锛屽啀鎵撳紑 `logs\` 鏌ョ湅褰撳ぉ鏃ュ織銆?
### `reports/latest.html` 鍦ㄥ摢閲?
璺緞涓洪」鐩牴鐩綍涓嬬殑 `reports\latest.html`銆?
### 鏃ュ織鍦ㄥ摢閲?
璺緞涓洪」鐩牴鐩綍涓嬬殑 `logs\` 鐩綍銆?