"""Confirmation du périmètre et présentation produit. Auteur : Onlyrutsuu."""
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLabel, QVBoxLayout, QWidget)

from core import config
from core.models import Plan


class ConfirmDialog(QDialog):
    def __init__(self, plan: Plan, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirmer le scan")
        self.setMinimumWidth(445)
        layout = QVBoxLayout(self)
        title = QLabel("Autorisation de scan")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.addRow("Interface", QLabel(f"{plan.adapter.name}  ·  {plan.adapter.address}"))
        form.addRow("Périmètre", QLabel(f"{plan.network}  ·  {len(plan.targets)} adresse(s)"))
        form.addRow("Découverte", QLabel("ARP local, puis ICMP si nécessaire"))
        form.addRow("Ports TCP", QLabel(", ".join(map(str, plan.ports)) or "Désactivés"))
        dns = "Désactivé"
        if plan.dns_enabled:
            dns = "Cache local" + (f" et PTR vers {plan.dns_server}" if plan.dns_server else " uniquement")
        form.addRow("DNS", QLabel(dns))
        form.addRow("Délai ICMP / TCP / DNS", QLabel(f"{plan.timeout_ms} ms"))
        layout.addLayout(form)
        warning = QLabel("Lance ce scan uniquement sur un réseau que tu administres ou pour lequel "
                         "le responsable t’a donné son accord.")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.check = QCheckBox("Je suis autorisé à inventorier cette plage.")
        layout.addWidget(self.check)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        self.launch = buttons.addButton("Lancer le scan", QDialogButtonBox.ButtonRole.AcceptRole)
        self.launch.setObjectName("primary")
        self.launch.setEnabled(False)
        self.check.toggled.connect(self.launch.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class About(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        head = QLabel("À propos")
        head.setObjectName("pageTitle")
        layout.addWidget(head)
        label = QLabel(f"RUX {config.VERSION}   ·   {config.AUTHOR}")
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        for paragraph in (
            "RUX inventorie les appareils observés sur un segment IPv4 privé directement connecté. "
            "Chaque scan nécessite ton accord pour l’interface, la plage et les méthodes affichées.",
            "Utilise RUX sur tes propres réseaux ou avec l’autorisation du responsable. "
            "Un pare-feu, la veille, l’isolation Wi-Fi ou un proxy ARP peuvent limiter la précision.",
            "Le fabricant présumé provient du préfixe MAC. Une MAC privée ou aléatoire peut rester "
            "inconnue. Un délai TCP expiré est affiché comme indéterminé.",
            "Les dates de la table utilisent l’heure locale. Les exports utilisent UTC. "
            "L’historique et le journal sont stockés dans %LOCALAPPDATA%\\RUX.",
            "Technologies : Python, Qt for Python et PyInstaller. Les attributions du registre "
            "et des composants sont détaillées dans data/NOTICE.txt et le projet source.",
        ):
            text = QLabel(paragraph)
            text.setWordWrap(True)
            layout.addWidget(text)
        layout.addStretch()
