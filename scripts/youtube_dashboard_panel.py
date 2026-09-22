"""Public dashboard navigation only. Never read credentials or contact localhost."""

def youtube_settings_panel():
    return '''
    <style>
      .yt-settings{border:1px solid #e4dcef;border-radius:18px;padding:22px;background:#fcfaff;margin:20px 0}
      .yt-settings h2{margin:0 0 8px;font-size:22px}.yt-settings p{line-height:1.65;margin:8px 0;color:#59516b}
      .yt-settings .yt-tag{display:inline-block;background:#ede5fb;border-radius:20px;padding:5px 11px;font-size:12px;margin:3px 6px 10px 0}
      .yt-settings .yt-links{display:flex;flex-wrap:wrap;gap:10px;margin:15px 0}
      .yt-settings .yt-button{display:inline-flex;align-items:center;justify-content:center;min-height:46px;border-radius:11px;padding:12px 17px;background:#d9ccf3;color:#312445;text-decoration:none;font-weight:650}
      .yt-settings .yt-secondary{background:#eaf2fc;color:#364b61}.yt-settings .yt-note{font-size:13px;color:#736680}
      .yt-settings details{margin-top:14px;line-height:1.7}.yt-settings summary{cursor:pointer;font-weight:650;min-height:30px}
      .yt-settings code{font-size:12px;overflow-wrap:anywhere}.yt-settings pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:#f1edf7;border-radius:10px}
      html:not([lang=en]) .yt-settings .yt-en{display:none}html[lang=en] .yt-settings .yt-ko{display:none}
      @media(max-width:600px){.yt-settings{padding:18px}.yt-settings .yt-button{flex:1 1 180px}}
    </style>
    <section class="yt-settings" id="youtube-settings" aria-label="YouTube connection settings">
      <h2>YouTube · Shorts</h2>
      <div><span class="yt-tag">English only</span><span class="yt-tag">macOS Keychain</span><span class="yt-tag"><span class="yt-ko">주 3회 운영</span><span class="yt-en">Three videos a week</span></span></div>
      <p><span class="yt-ko">YouTube 연결과 상태 확인은 녹화·업로드를 실행하는 Mac에서 진행해요. 이 공개 대시보드에는 비밀값을 입력하지 않아요.</span><span class="yt-en">Connect and check YouTube on the Mac that records and uploads your videos. This public dashboard never asks for YouTube secrets.</span></p>
      <div class="yt-links">
        <a id="youtube-connect" class="yt-button" href="onnellab-content://youtube/connect"><span class="yt-ko">이 Mac에서 YouTube 연결</span><span class="yt-en">Connect YouTube on this Mac</span></a>
        <a id="youtube-check" class="yt-button yt-secondary" href="onnellab-content://youtube/status"><span class="yt-ko">연결 상태 · 테스트</span><span class="yt-en">Connection status · Test</span></a>
      </div>
      <p class="yt-note"><span class="yt-ko">연결 상태와 통계는 위 ONNELLAB Media Console 영역에 자동 표시돼요. OAuth 재연결이나 권한 변경이 필요할 때만 이 버튼으로 작업용 Mac의 로컬 연결 화면을 열어 주세요.</span><span class="yt-en">Connection status and metrics are auto-published in the ONNELLAB Media Console section above. Open the local console on the worker Mac only when OAuth reconnection or permission changes are needed.</span></p>
      <hr style="border:0;border-top:1px solid #e6dfec;margin:20px 0">
      <h2>Lyria 3 Pro · Aether Inn</h2>
      <div><span class="yt-tag">Google Cloud</span><span class="yt-tag">Official API</span><span class="yt-tag"><span class="yt-ko">화·토 오전 9시 예약발행</span><span class="yt-en">Tue · Sat · 09:00 scheduled publish</span></span></div>
      <p><span class="yt-ko">Aether Inn 신곡은 Lyria 3 Pro 후보를 만들고 Gemini 2.5 Flash로 실제 음원을 품질 검토한 뒤, Gemini 2.5 Flash Image로 풍경 커버를 생성하고 고정 타이포를 합성해 영상 렌더와 Aether Inn YouTube 업로드까지 이어져요. 공개 대시보드에는 Google 인증정보를 입력하지 않고, 작업용 Mac의 ADC를 사용합니다.</span><span class="yt-en">Aether Inn singles use Lyria 3 Pro, Gemini 2.5 Flash to review the actual generated audio, Gemini 2.5 Flash Image for the landscape cover, branded cover compositing, video rendering, and the Aether Inn YouTube uploader. Google credentials are never entered on this public dashboard; the worker Mac uses Application Default Credentials.</span></p>
      <div class="yt-links">
        <a id="lyria-connect" class="yt-button" href="onnellab-content://lyria/connect"><span class="yt-ko">Lyria 3 Pro 연결 · 자동화 설정</span><span class="yt-en">Lyria 3 Pro connection · Automation</span></a>
        <a class="yt-button yt-secondary" href="https://console.cloud.google.com/" target="_blank" rel="noopener noreferrer"><span class="yt-ko">Google Cloud 열기</span><span class="yt-en">Open Google Cloud</span></a>
      </div>
      <p class="yt-note"><span class="yt-ko">모델은 <code>lyria-3-pro-preview</code>, 위치는 <code>global</code>로 고정해요. Lyria 음악은 현재 공시 기준 전체 곡 1회당 US$0.08이며 로컬 비용 한도를 넘는 요청은 차단해요. 커버는 신곡당 Gemini 2.5 Flash Image 요청 1회로 제한합니다. 연결 확인은 유료 음악·이미지 생성을 실행하지 않아요.</span><span class="yt-en">The model is fixed to <code>lyria-3-pro-preview</code> in <code>global</code>. Lyria is currently published at US$0.08 per full-song generation and requests above the local music spend cap are blocked. Cover generation is limited to one Gemini 2.5 Flash Image request per new single. Connection checks trigger neither paid music nor image generation.</span></p>
      <details><summary><span class="yt-ko">처음 연결하거나 버튼이 열리지 않을 때</span><span class="yt-en">First-time setup or launcher not opening</span></summary>
        <p><span class="yt-ko">로컬 연결 도우미를 설치한 Mac에서는 위 버튼이 연결 화면을 열어요. 새 Mac에서는 저장소를 최신으로 받은 뒤 아래 명령으로 연결 실행기를 한 번만 설치해요.</span><span class="yt-en">The buttons open the installed local helper. On a new Mac, update the repository and install the launcher once:</span></p>
        <pre><code>cd ~/Projects/onnel-content-engine
python3 -B scripts/install_youtube_connect.py</code></pre>
        <p><span class="yt-ko">로컬 화면에서 Google Cloud의 Desktop OAuth JSON과 ONNELLAB 채널 ID를 넣고 Google 로그인·권한 동의를 진행해요. 최초 설정 뒤에는 예약 작업이 같은 Keychain을 사용해요.</span><span class="yt-en">In the local console, import the Google Cloud Desktop OAuth JSON and expected ONNELLAB channel ID, then complete Google sign-in and consent. Scheduled runs use that same Keychain afterward.</span></p>
        <p><span class="yt-ko">도우미 직접 열기:</span><span class="yt-en">Open the consoles directly:</span></p>
        <pre><code>python3 -B scripts/short_video_connect.py open
python3 -B scripts/lyria_connect.py open</code></pre>
        <p class="yt-note"><span class="yt-ko">Lyria 최초 인증은 Mac 터미널에서 <code>gcloud auth application-default login</code> 후 <code>gcloud auth application-default set-quota-project PROJECT_ID</code>를 실행해요. 토큰은 /ops/나 GitHub에 저장하지 않습니다.</span><span class="yt-en">For first-time Lyria authentication, run <code>gcloud auth application-default login</code> and then <code>gcloud auth application-default set-quota-project PROJECT_ID</code> on the Mac. Tokens are never stored in /ops/ or GitHub.</span></p>
        <p class="yt-note"><span class="yt-ko">Google 로그인과 최초 권한 동의는 한 번 필요해요. 인증 성공이 API 프로젝트의 공개 업로드 제한 해제를 뜻하지는 않아요.</span><span class="yt-en">Initial Google consent is required once. Authentication success does not lift an API project's private-upload restriction.</span></p>
      </details>
    </section>
'''.strip()
