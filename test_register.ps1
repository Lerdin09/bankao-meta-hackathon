$body = '{"email":"teste.kyc@bankao.ao","telefone":"+244923000001","password":"Teste12345","confirm_password":"Teste12345","terms_accepted":true}'
$res = Invoke-RestMethod -Uri 'http://localhost:8000/api/auth/register' -Method POST -ContentType 'application/json' -Body $body
Write-Host "Token: $($res.access_token.Substring(0,20))..."
Write-Host "KYC Status: $($res.user.kyc_status)"
Write-Host "User ID: $($res.user.id)"
