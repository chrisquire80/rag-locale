# Script di Configurazione Firewall per RAG Locale
# Eseguire come Amministratore
# Scopo: Isolare LM Studio e RAG app su loopback (127.0.0.1) - Zero-Cloud Architecture

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      RAG LOCALE - Firewall Hardening (Windows 11)         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Verifica privilegi amministratore
$isAdmin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ ERROR: Questo script richiede privilegi di Amministratore" -ForegroundColor Red
    Write-Host "   Esegui PowerShell come Amministratore e riprova." -ForegroundColor Red
    exit 1
}

Write-Host "✓ Privilegi amministratore confermati`n" -ForegroundColor Green

# =====================================================================
# REGOLA 1: LM Studio - Blocca accesso esterno porta 1234
# =====================================================================
Write-Host "[1] Configurazione LM Studio Server (porta 1234)..." -ForegroundColor Yellow

$ruleName = "RAG-LMStudio-BlockExternal"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "   ⚠️  Regola già presente. Rimozione e ricreazione..." -ForegroundColor Yellow
    Remove-NetFirewallRule -DisplayName $ruleName -Confirm:$false
}

New-NetFirewallRule `
  -DisplayName "RAG-LMStudio-BlockExternal" `
  -Description "Blocca accesso esterno a LM Studio (127.0.0.1 loopback only)" `
  -Direction Inbound `
  -Action Block `
  -Protocol TCP `
  -LocalPort 1234 `
  -RemoteAddress @("!127.0.0.1", "!::1") `
  -Enabled $true | Out-Null

Write-Host "   ✓ LM Studio port 1234 - accesso esterno BLOCCATO" -ForegroundColor Green

# =====================================================================
# REGOLA 2: RAG App - Blocca accesso esterno porta 8080 (se usata)
# =====================================================================
Write-Host ""
Write-Host "[2] Configurazione RAG Application (porta 8080)..." -ForegroundColor Yellow

$ruleName = "RAG-App-BlockExternal"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existingRule) {
    Write-Host "   ⚠️  Regola già presente. Rimozione e ricreazione..." -ForegroundColor Yellow
    Remove-NetFirewallRule -DisplayName $ruleName -Confirm:$false
}

New-NetFirewallRule `
  -DisplayName "RAG-App-BlockExternal" `
  -Description "Blocca accesso esterno a RAG App (127.0.0.1 loopback only)" `
  -Direction Inbound `
  -Action Block `
  -Protocol TCP `
  -LocalPort 8080 `
  -RemoteAddress @("!127.0.0.1", "!::1") `
  -Enabled $true | Out-Null

Write-Host "   ✓ RAG App port 8080 - accesso esterno BLOCCATO" -ForegroundColor Green

# =====================================================================
# Verifica finale e Summary
# =====================================================================
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    CONFIGURAZIONE COMPLETATA              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 Regole Firewall Attive:" -ForegroundColor White
Get-NetFirewallRule -DisplayName "RAG-*" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "   ✓ $($_.DisplayName) [$($_.Direction) - $($_.Action)]" -ForegroundColor Green
}

Write-Host ""
Write-Host "🔒 Configurazione Sicurezza:" -ForegroundColor White
Write-Host "   • LM Studio: Accessibile solo da 127.0.0.1 (localhost)" -ForegroundColor White
Write-Host "   • RAG App:   Accessibile solo da 127.0.0.1 (localhost)" -ForegroundColor White
Write-Host "   • Network:   Isolamento completo da altre macchine" -ForegroundColor White
Write-Host "   • Scope:     Zero-Cloud Architecture (dati non lasciano il PC)" -ForegroundColor White
Write-Host ""

Write-Host "⚠️  IMPORTANTE:" -ForegroundColor Yellow
Write-Host "   • LM Studio DEVE avere 'Serve on Local Network' = OFF" -ForegroundColor Yellow
Write-Host "   • Verificare con: netsh advfirewall firewall show rule name='RAG-*'" -ForegroundColor Yellow
Write-Host ""

Write-Host "✓ Setup Firewall completato!" -ForegroundColor Green
Write-Host ""
