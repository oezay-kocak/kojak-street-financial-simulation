# PowerShell Skript: Python-Dateien (.py) zu Textdateien (.txt) konvertieren
# Kodierung: UTF-8

# Verzeichnis festlegen (aktuelles Verzeichnis)
$path = Get-Location

# Alle .py Dateien im Verzeichnis suchen
$files = Get-ChildItem -Path $path -Filter *.py

foreach ($file in $files) {
    # Zielpfad für die .txt Datei erstellen
    $newFileName = $file.FullName -replace '\.py$', '.txt'
    
    # Inhalt lesen und in UTF-8 kodiert in die neue Datei schreiben
    Get-Content -Path $file.FullName -Raw | Set-Content -Path $newFileName -Encoding UTF8
    
    Write-Host "Konvertiert: $($file.Name) -> $($newFileName | Split-Path -Leaf)"
}

Write-Host "Fertig! Alle Dateien wurden verarbeitet."
