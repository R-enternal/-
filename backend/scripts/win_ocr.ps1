# Temporary: OCR rendered PDF pages using Windows built-in OCR (zh-Hans)
param(
    [string]$ImageDir = "C:\temp_pdf_ocr",
    [string]$OutFile = ""
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]

function Await($WinRtTask, $ResultType) {
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
    $netTask = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

$lang = [Windows.Globalization.Language]::new("zh-Hans")
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) {
    Write-Output "ERROR: zh-Hans OCR engine not available"
    exit 1
}

$images = Get-ChildItem -Path $ImageDir -Filter "*.png" | Sort-Object Name
if ([string]::IsNullOrEmpty($OutFile)) {
    $OutFile = Join-Path $env:TEMP "plan2_ocr.txt"
}
$sb = New-Object System.Text.StringBuilder
foreach ($img in $images) {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($img.FullName)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $null = $sb.AppendLine("===== $($img.BaseName) =====")
    $null = $sb.AppendLine($result.Text)
}
[System.IO.File]::WriteAllText($OutFile, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
Write-Output ("OCR done, images: " + $images.Count)
