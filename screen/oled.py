from machine import Pin, I2C
from screen.oled_library import SSD1306_I2C
from pins import OLED_SCL_PIN, OLED_SDA_PIN

# Emojis/Smileys en format bitmap (16x16) - Taille grande

EMOJI_SMILE = [
    "0000000000000000",
    "0000111110000000",
    "0011110011110000",
    "0111000000111000",
    "1110000000001110",
    "1100011001100011",
    "1100011001100011",
    "1110000000001110",
    "1110011111100011",
    "1110011111100011",
    "0111100000111000",
    "0011110011110000",
    "0000111110000000",
    "0000000000000000",
    "0000000000000000",
    "0000000000000000",
]

EMOJI_HAPPY = [
    "0001111111110000",
    "0011111111111000",
    "0111110000111100",
    "1111100000001111",
    "1111000000000111",
    "1110011110011011",
    "1110111110111011",
    "1110011110011011",
    "1111000000000111",
    "1111100000001111",
    "0111110000111100",
    "0011111111111000",
    "0001111111110000",
    "0000000000000000",
    "0000000000000000",
    "0000000000000000",
]

EMOJI_SAD = [
    "0001111111110000",
    "0011111111111000",
    "0111110000111100",
    "1111100000001111",
    "1111000000000111",
    "1110011100011011",
    "1110111100111011",
    "1110011100011011",
    "1111000000000111",
    "1111011111001111",
    "0111110000111100",
    "0011111111111000",
    "0001111111110000",
    "0000000000000000",
    "0000000000000000",
    "0000000000000000",
]

EMOJI_CHESHIRE_GRIN = [
    "0000000000000000",
    "0000111111110000",
    "0011111111111100",
    "0111110011111110",
    "1111000000011111",
    "1110011001100111",
    "1110100100010111",
    "1111000000001111",
    "1111111111111111",
    "1111111111111111",
    "1111111111111111",
    "0111111111111110",
    "0011111111111100",
    "0001111111110000",
    "0000111111100000",
    "0000000000000000",
]

EMOJI_HEART = [
    "0011001100110000",
    "0111111111111000",
    "1111111111111100",
    "1111111111111110",
    "1111111111111110",
    "1111111111111110",
    "0111111111111100",
    "0011111111111000",
    "0001111111110000",
    "0000111111100000",
    "0000011111000000",
    "0000001110000000",
    "0000000100000000",
    "0000000000000000",
    "0000000000000000",
    "0000000000000000",
]

EMOJI_FIRE = [
    "0000001100000000",
    "0000011110000000",
    "0000111110000000",
    "0001111111000000",
    "0011111111100000",
    "0111111111110000",
    "0111101011110000",
    "1111110111111000",
    "1111111111111000",
    "0111111111110000",
    "0011110111100000",
    "0001110011000000",
    "0000110011000000",
    "0000010001000000",
    "0000000000000000",
    "0000000000000000",
]

EMOJI_STAR = [
    "0000001000000000",
    "0000001000000000",
    "0000011100000000",
    "0000011100000000",
    "0001111110000000",
    "0001111110000000",
    "0111111111100000",
    "1111111111110000",
    "0111111111100000",
    "0011111111000000",
    "0000111100000000",
    "0000111100000000",
    "0000011000000000",
    "0000011000000000",
    "0000000000000000",
    "0000000000000000",
]


class OLED:
    """Classe pour gérer l'écran OLED SSD1306."""

    def __init__(self,
                 width: int = 128,
                 height: int = 32,
                 scl_pin: int = OLED_SCL_PIN,
                 sda_pin: int = OLED_SDA_PIN):
        """Initialise l'écran OLED.

        Args:
            width: Largeur de l'écran (128 par défaut)
            height: Hauteur de l'écran (32 par défaut)
            scl_pin: Broche GPIO pour SCL (7 par défaut)
            sda_pin: Broche GPIO pour SDA (6 par défaut)
        """
        self.width = width
        self.height = height

        # Configuration de l'I2C
        self.i2c = I2C(scl=Pin(scl_pin), sda=Pin(sda_pin), freq=400000)

        # Initialiser l'écran OLED
        self.oled = SSD1306_I2C(width, height, self.i2c)

        # Effacer l'écran
        self.clear()
        print("✅ Écran OLED initialisé")

    def clear(self) -> None:
        """Efface l'écran."""
        self.oled.fill(0)
        self.oled.show()

    def set_text(self, first_line: str, second_line: str = "", third_line: str = "") -> None:
        """Affiche du texte sur 3 lignes.

        Args:
            first_line: Texte de la première ligne
            second_line: Texte de la deuxième ligne (optionnel)
            third_line: Texte de la troisième ligne (optionnel)
        """
        self.clear()

        # Afficher la première ligne
        if first_line:
            self.oled.text(first_line[:16], 0, 0)

        # Afficher la deuxième ligne
        if second_line:
            self.oled.text(second_line[:16], 0, 10)

        # Afficher la troisième ligne
        if third_line:
            self.oled.text(third_line[:16], 0, 20)

        self.oled.show()

    def draw_emoji(self, x: int, y: int, emoji_data: list) -> None:
        """Dessine un emoji à partir de données bitmap.

        Args:
            x: Position X
            y: Position Y
            emoji_data: Liste des lignes du bitmap
        """
        for row, line in enumerate(emoji_data):
            for col, pixel in enumerate(line):
                if pixel == '1':
                    self.oled.pixel(x + col, y + row, 1)

    def smiling_emoticon(self) -> None:
        """Affiche un smiley heureux au centre de l'écran."""
        self.clear()

        # Centrer l'emoji (16x16) sur l'écran (128x32)
        x = (self.width - 16) // 2
        y = (self.height - 16) // 2

        self.draw_emoji(x, y, EMOJI_HAPPY)
        self.oled.show()

    def sad_emoticon(self) -> None:
        """Affiche un smiley triste au centre de l'écran."""
        self.clear()

        # Centrer l'emoji (16x16) sur l'écran (128x32)
        x = (self.width - 16) // 2
        y = (self.height - 16) // 2

        self.draw_emoji(x, y, EMOJI_SAD)
        self.oled.show()

    def cheshire_grin(self) -> None:
        """Affiche le sourire du chat de Cheshire au centre de l'écran."""
        self.clear()

        # Centrer l'emoji (16x16) sur l'écran (128x32)
        x = (self.width - 16) // 2
        y = (self.height - 16) // 2

        self.draw_emoji(x, y, EMOJI_CHESHIRE_GRIN)
        self.oled.show()

    def show_emoji(self, emoji_data: list, x: int = None, y: int = None) -> None:
        """Affiche un emoji personnalisé.

        Args:
            emoji_data: Données de l'emoji en bitmap
            x: Position X (centré par défaut)
            y: Position Y (centré par défaut)
        """
        self.clear()

        if x is None:
            x = (self.width - 16) // 2
        if y is None:
            y = (self.height - 16) // 2

        self.draw_emoji(x, y, emoji_data)
        self.oled.show()

    def show_emojis_row(self, emoji_list: list) -> None:
        """Affiche plusieurs emojis en ligne.

        Args:
            emoji_list: Liste de tuples (emoji_data, x, y)
        """
        self.clear()

        for emoji_data, x, y in emoji_list:
            self.draw_emoji(x, y, emoji_data)

        self.oled.show()

    def show(self) -> None:
        """Met à jour l'affichage."""
        self.oled.show()

