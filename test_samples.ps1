$r = Invoke-RestMethod -Uri 'http://localhost:8000/api/kyc/samples/bilhete'
Write-Host "doc_type: $($r.doc_type)"
Write-Host "frente len: $($r.foto_frente.Length)"
Write-Host "verso len: $($r.foto_verso.Length)"
