# Security

ReconTrail 0.1.0 is a **single-user local workbench**, not an internet-facing, multi-tenant, or hosted image-processing service. It binds to `127.0.0.1`. Do not expose it through a reverse proxy, port forwarding, or a modified bind address.

## Trust boundaries

The workbench uses a random capability token, checks Host/Origin, limits request bodies and job counts, restricts downloadable artifact names, and launches workers without shell command interpolation. Pixel, image-count, and upload limits reduce resource exposure; they do not sandbox native decoders. Pillow, OpenCV, and video codecs run with the current user's permissions. Keep dependencies updated and process trusted captures only.

The local access token starts in the URL fragment and is stored in browser sessionStorage. Do not share that link or terminal screenshots containing the token. The project directory retains original uploads and logs; it does not automatically sync them to a cloud service or delete them. Original photographs can include device/location metadata. Normalized PNG exports omit EXIF, but input copies still need your own retention policy.

Reports include source filenames, capture diagnostics, geometry, camera data, and parameters. Review them before sharing. CLI output and error logs may expose local paths. These controls do not replace operating-system permissions, disk quotas, malware protection, or secret scanning.

## Reporting a vulnerability

Private vulnerability reporting has not been verified as enabled for this repository. Do not publish working access tokens, private captures, or sensitive exploit details in a public issue. A non-sensitive contact request can be used to establish a private reporting channel with the maintainer. Update this section when a verified private reporting route is available.

No independent security audit or penetration test has been completed. The tests in `tests/test_server.py` establish only their specific checked cases.

## 中文说明

本项目仅供单用户本机使用，不要暴露到公网。原生图片和视频解码器未沙箱化，请使用可信文件并保持依赖更新。不要分享访问令牌、原始照片或含敏感路径的日志；输入副本会保留在工作目录，标准化导出不含 EXIF，离线报告仍可能包含源文件名和场景信息。仓库私有漏洞报告渠道尚未确认启用，公开 Issue 中请勿发布有效令牌或敏感利用细节。尚无独立安全审计。
