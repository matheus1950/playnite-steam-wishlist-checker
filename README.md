# Steam Wishlist × Playnite

[Português (Brasil)](README.pt-BR.md)

A Windows desktop app that helps you find games still present in your Steam wishlist that you already own in other libraries connected to Playnite, such as Epic Games, GOG, Amazon Games, Xbox, EA app, Battle.net and others.

## Features

- Dark mode graphical interface
- Automatic Playnite library reading
- Playnite integration through a custom plugin
- Plugin installation directly from the app
- Persistent SteamID64 configuration
- Steam wishlist vs. Playnite library comparison
- Ignores games from your own Steam library
- Shows which library each match was found in
- Exact and approximate matching
- Filter by library
- Filter by match type
- Search by game name
- Double-click to open the game's Steam page
- Standalone Windows executable

## Real-world result

The purpose of Wishlist Checker is to help identify games that remain in your Steam wishlist even though you already own them in another library registered in Playnite.

After running the comparison, you can review the matches and manually remove from your Steam wishlist the games you no longer need to track.

### Before

In this example, the wishlist contained **517 games**, and the app found **19 matches** with games already present in other libraries.

![Before cleaning the wishlist](resources/screenshots/antes.jpeg)

### After

After reviewing the results, running the check again, and manually removing some games that were already owned, the wishlist was reduced to **484 games**, with only **2 remaining matches**.

![After cleaning the wishlist](resources/screenshots/depois.jpeg)

> Wishlist Checker does not automatically remove games from your Steam account. It only identifies possible matches so you can review them and decide which items you want to remove manually from your wishlist.

## Requirements

To use the distributed version:

- Windows
- Playnite installed
- Steam account with an accessible wishlist
- Internet connection

Python, Visual Studio and the Playnite Interactive SDK are not required.

## Download
## Download
Download the latest version from the GitHub **Releases** section.

Extract the ZIP file to a folder of your choice and run:

```text
WishlistSteamCheck.exe

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.