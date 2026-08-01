Primeiro Commit.


Script SDK playnite:


        Connected to Playnite process.
        Use CTLR-V and ENTER to paste commands to initialize basic SDK variables.
        More information at:
        https://playnite.link/docs/master/tutorials/extensions/scriptingDebugging.html

[Processo:24444]: PS C:\Users\mathe\OneDrive\Documentos> $PlayniteRunspace = Get-Runspace -Name 'PSInteractive'
[Processo:24444]: PS C:\Users\mathe\OneDrive\Documentos> $PlayniteApi = $PlayniteRunspace.SessionStateProxy.GetVariable('PlayniteApi')
[Processo:24444]: PS C:\Users\mathe\OneDrive\Documentos> $PlayniteApi.Database.Games.Count
1905
[Processo:24444]: PS C:\Users\mathe\OneDrive\Documentos> $PlayniteApi.Database.Games | ForEach-Object { [PSCustomObject]@{ Name=$_.Name; Source=if ($_.Source) {$_.Source.Name} else {""}; PluginId="$($_.PluginId)"; GameId="$($_.GameId)"; IsInstalled=$_.IsInstalled; Hidden=$_.Hidden } } | ConvertTo-Json -Depth 4 | Set-Content "$env:APPDATA\Playnite\steam_wishlist_checker_library.json" -Encoding UTF8
[Processo:24444]: PS C:\Users\mathe\OneDrive\Documentos>


Imagem exemplo de funcionamento:
<img width="1574" height="1013" alt="image" src="https://github.com/user-attachments/assets/6da84aa4-03b0-4d3e-994e-e617a2ca0d29" />

