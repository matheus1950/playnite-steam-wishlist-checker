using Playnite.SDK;
using Playnite.SDK.Events;
using Playnite.SDK.Plugins;
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows.Controls;

namespace SteamWishlistExporter
{
    public class SteamWishlistExporter : GenericPlugin
    {
        private static readonly ILogger logger = LogManager.GetLogger();

        private SteamWishlistExporterSettingsViewModel settings { get; set; }

        public override Guid Id { get; } =
            Guid.Parse("f69bad44-bb27-4d8c-b6ae-fac43d72aa4d");

        public SteamWishlistExporter(IPlayniteAPI api) : base(api)
        {
            settings = new SteamWishlistExporterSettingsViewModel(this);

            Properties = new GenericPluginProperties
            {
                HasSettings = true
            };
        }


        // ====================================================
        // PLAYNITE INICIADO
        // ====================================================

        public override void OnApplicationStarted(
            OnApplicationStartedEventArgs args
        )
        {
            ExportLibrary();
        }


        // ====================================================
        // BIBLIOTECA ATUALIZADA
        // ====================================================

        public override void OnLibraryUpdated(
            OnLibraryUpdatedEventArgs args
        )
        {
            ExportLibrary();
        }


        // ====================================================
        // EXPORTAÇÃO
        // ====================================================

        private void ExportLibrary()
        {
            try
            {
                var appDataDirectory =
                    Environment.GetFolderPath(
                        Environment.SpecialFolder.ApplicationData
                    );

                var playniteDirectory =
                    Path.Combine(
                        appDataDirectory,
                        "Playnite"
                    );

                var exportFile =
                    Path.Combine(
                        playniteDirectory,
                        "steam_wishlist_checker_library.json"
                    );


                // ============================================
                // LÊ TODOS OS JOGOS DO PLAYNITE
                // ============================================

                var games =
                    PlayniteApi
                    .Database
                    .Games
                    .Select(game => new
                    {
                        Name =
                            game.Name ?? "",

                        Source =
                            game.Source != null
                                ? game.Source.Name ?? ""
                                : "",

                        PluginId =
                            game.PluginId.ToString(),

                        GameId =
                            game.GameId ?? "",

                        IsInstalled =
                            game.IsInstalled,

                        Hidden =
                            game.Hidden
                    })
                    .ToList();


                // ============================================
                // CONVERTE PARA JSON
                // ============================================

                var json =
                    Playnite.SDK.Data.Serialization.ToJson(
                        games,
                        true
                    );


                // ============================================
                // GARANTE QUE A PASTA EXISTE
                // ============================================

                Directory.CreateDirectory(
                    playniteDirectory
                );


                // ============================================
                // ESCREVE O ARQUIVO
                // UTF-8 SEM BOM
                // ============================================

                File.WriteAllText(
                    exportFile,
                    json,
                    new UTF8Encoding(false)
                );


                // ============================================
                // LOG
                // ============================================

                logger.Info(
                    $"Steam Wishlist Exporter: " +
                    $"{games.Count} jogos exportados para " +
                    $"{exportFile}"
                );
            }
            catch (Exception ex)
            {
                logger.Error(
                    ex,
                    "Steam Wishlist Exporter: " +
                    "erro ao exportar a biblioteca."
                );
            }
        }


        // ====================================================
        // SETTINGS
        // ====================================================

        public override ISettings GetSettings(
            bool firstRunSettings
        )
        {
            return settings;
        }


        public override UserControl GetSettingsView(
            bool firstRunSettings
        )
        {
            return new SteamWishlistExporterSettingsView();
        }
    }
}