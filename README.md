# Rux-Terminal

**RUX · Inventaire du réseau local pour Windows x64 · version 1.0.0 · Onlyrutsuu**

Le dépôt utilise la [licence MIT](LICENSE). Les attributions des composants tiers figurent dans [data/NOTICE.txt](data/NOTICE.txt).

RUX affiche les appareils observés sur un segment IPv4 privé. Il est conçu pour un compte standard, avec une interface en français et un registre de fabricants hors ligne.

<h2 align="center">Démarrage // Utiliser RUX.exe</h2>

1. Extrais l’archive dans un dossier où ton compte peut écrire. Ouvre **RUX.exe**.
2. Choisis la carte reliée au LAN. Sur un poste avec Wi-Fi, Ethernet et VMware, vérifie le nom de la carte et son IPv4. Le préfixe réel apparaît à côté de l’adresse.
3. Vérifie la plage proposée. Sur `10.30.45.6/16`, par exemple, RUX propose `10.30.45.0/24`. Tu peux choisir une autre tranche de ce LAN. Un `/24` représente 256 adresses et, sur un réseau classique, 254 cibles hôtes.
4. Laisse les options par défaut pour commencer. Clique sur **Lancer le scan**, relis le récapitulatif, coche l’autorisation et confirme. Tu peux annuler à tout moment.
5. Clique sur les en-têtes pour trier. Le champ de recherche filtre toutes les colonnes. **Exporter** enregistre l’inventaire entier du scan affiché. Le filtre visuel reste indépendant de l’export.
6. Ouvre **Journal** pour consulter les erreurs, les permissions manquantes et les résultats partiels.

L’exécutable embarque Python, Qt et le registre OUI. Un scan nécessite une carte Ethernet, Wi-Fi ou un agrégat Ethernet actif avec une IPv4 RFC 1918. Cible de recette : Windows 10 22H2 et Windows 11 x64.

<h2 align="center">Vérification // Auteur et intégrité du fichier</h2>

**Onlyrutsuu** figure dans les en-têtes du code RUX, les métadonnées Python, l’écran **À propos**, les exports JSON et la ressource de version Windows. Dans les propriétés du fichier, ouvre l’onglet **Détails**. Le binaire fourni porte ces crédits d’auteur et est distribué sans certificat Authenticode.

Dans PowerShell, depuis le dossier contenant l’exécutable :

```powershell
(Get-Item .\RUX.exe).VersionInfo | Select-Object CompanyName, FileDescription, ProductVersion, LegalCopyright
(Get-AuthenticodeSignature .\RUX.exe).Status
$attendu = ((Get-Content .\RUX.exe.sha256 -Raw).Trim() -split '\s+')[0]
(Get-FileHash .\RUX.exe -Algorithm SHA256).Hash -eq $attendu
```

Le dernier contrôle doit afficher `True`. L’empreinte permet de détecter une différence avec le binaire livré. Pour contrôler le démarrage, Qt, SQLite, les ressources et l’énumération locale des cartes sans envoyer de sonde :

```powershell
$p = Start-Process .\RUX.exe -ArgumentList '--self-test','rux-verification.json' -Wait -PassThru
$p.ExitCode
Get-Content .\rux-verification.json
```

Le rapport décrit **le poste qui a exécuté le test**. Le code de sortie attendu est `0` et `ok` doit valoir `true`.

<h2 align="center">Installation // Lancer depuis les sources</h2>

Utilise Python 3.12 **x64** pour le build de référence. Les versions 3.11 à 3.14 entrent dans la plage du projet. Les commandes suivantes s’exécutent depuis le dossier contenant `pyproject.toml`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe main.py
```

La seule dépendance applicative directe est `PySide6-Essentials==6.10.3`, la distribution officielle qui fournit notamment QtCore, QtGui, QtWidgets et dépend de Shiboken6. Les accès réseau reposent sur la bibliothèque standard et les API de Windows. SQLite est inclus avec CPython.

<h2 align="center">Build Windows // Produire RUX.exe</h2>

Depuis PowerShell, la procédure complète tient en une commande :

```powershell
.\Build-RUX.cmd
```

Le script prépare le venv, installe les dépendances, exécute les tests, construit le binaire graphique, lance son auto-test, puis calcule son SHA-256. Les sorties sont `dist\RUX.exe`, `dist\RUX.exe.sha256` et `.pyi-work\self-test.json`. Le premier build nécessite Internet pour installer les paquets Python.

Pour exécuter séparément les étapes de développement :

```powershell
.\.venv\Scripts\python.exe -m pip install ".[build]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --workpath .\.pyi-work --distpath .\dist .\build\RUX.spec
```

`RUX.spec` fixe le mode mono-fichier graphique, l’icône, les données, les notices et les propriétés Windows. PyInstaller est épinglé en version 6.22.3. Le workflow **Build RUX Windows x64**, lancé sur les changements de main, les pull requests ou manuellement, exécute le même script sur un runner Windows et conserve l’exécutable, l’empreinte et le rapport. Pour l’utiliser, place le **contenu des sources** à la racine de ton dépôt, puis utilise **Actions → Build RUX Windows x64 → Run workflow**.

<h2 align="center">Architecture // Agents et interface</h2>

Qt Widgets fournit la table modèle/vue et le filtrage. Le cœur fonctionne sans Qt. Le thread GUI reçoit les observations et la progression par signaux. L’orchestrateur utilise un seul pool de huit workers et lui soumet au plus huit adresses à la fois.

| Agent | Rôle |
|---|---|
| `agents/orchestrator.py` | Consomme la confirmation à usage unique, distribue les cibles, gère annulation, erreurs et historique. |
| `agents/discovery.py` | Constate la présence du poste local, d’une réponse ARP fraîche ou d’un Echo Reply. |
| `agents/identification.py` | Enrichit les hôtes observés par DNS, OUI et, sur demande, TCP. |
| `agents/report.py` | Fournit une représentation commune à la table et aux exports. |

```text
main.py                        Point d’entrée graphique et auto-test
agents/                        orchestrator.py, discovery.py, identification.py, report.py
skills/                        arp.py, icmp.py, tcp.py, dns.py, oui.py, exports.py, journal.py
core/                          config.py, models.py, scope.py, windows_net.py, inventory.py
gui/                           main_window.py, dialogs.py, worker.py, device_table.py, style.py
data/                          oui.csv, rux.ico, NOTICE.txt, licenses/
build/                         RUX.spec, version_info.txt, assemble_x64.py
tests/                         Périmètre, skills, historique, exports, agents, GUI et ABI Windows
.github/workflows/windows.yml  Build Windows manuel
Build-RUX.cmd                  Build local et auto-test de l’exécutable
pyproject.toml                 Version, auteur, paquets et dépendances
```

<h2 align="center">Skills // Entrées et sorties</h2>

Une `Session` contient le plan confirmé, l’interface source, les cibles et le signal d’annulation. Une sonde réseau vérifie l’appartenance au périmètre et la route directe avant émission. `TargetDenied` signale une destination refusée. `StopScan` interrompt la planification. Les erreurs système restent des `OSError` que les agents consignent.

| Fonction | Entrée | Résultat |
|---|---|---|
| `skill_arp_scan` | Session, IPv4 | MAC unicast obtenue via `ResolveIpNetEntry2` ou `None`. La résolution ARP rafraîchit le cache voisin de cette cible. |
| `skill_icmp_ping` | Session, IPv4 | Latence en millisecondes, zéro compris, ou `None`. `IcmpSendEcho2Ex` fixe l’IPv4 source et le délai. Après un Echo Reply, une lecture passive de la table des voisins peut fournir la MAC. |
| `skill_tcp_probe` | Session, hôte observé, port confirmé | `PortResult` avec `open`, `refused` ou `indeterminate`. Une erreur système est rapportée par l’agent. Ouverture et fermeture de connexion, sans données applicatives. |
| `skill_dns_resolve` | Session, IPv4 observée | Nom PTR ou `None`. Lit le cache via `DnsQuery_W` avec `DNS_QUERY_NO_WIRE_QUERY`. À défaut, interroge le premier DNS de la carte situé dans les cibles confirmées. La requête UDP directe ne demande pas de récursion. |
| `skill_oui_lookup` | MAC optionnelle, registre local | Titulaire du préfixe le plus spécifique (36, 28, puis 24 bits) ou `None`. Une MAC administrée localement reste sans fabricant présumé. |
| `skill_export_csv` | Dictionnaire de rapport, chemin | CSV avec BOM UTF-8, séparateur point-virgule, ligne de résumé et une ligne par hôte. Renvoie le nombre d’hôtes. Les textes pouvant être interprétés comme des formules sont neutralisés. |
| `skill_export_json` | Même entrée | Document JSON UTF-8 avec métadonnées du scan et observations. Renvoie le nombre d’hôtes. |
| `skill_logging` | Logger, niveau, identifiant de scan, message | Événement UTC dans la vue Journal et dans le fichier tournant si le dossier utilisateur est accessible. |

Les exports utilisent un fichier temporaire situé à côté de la destination puis un remplacement atomique. Une erreur d’écriture avant le remplacement conserve la version précédente.

<h2 align="center">Paramètres // Réseau et stockage</h2>

| Paramètre | Valeur initiale |
|---|---|
| Plages acceptées | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`. La plage complète doit aussi appartenir au segment de la carte sélectionnée. |
| Cibles | 256 adresses au maximum par scan, avec traitement des réseaux `/31` et `/32`. |
| Concurrence | 8 opérations au maximum, toutes méthodes confondues. |
| TCP | Désactivé. Si activé, ports 80 et 443 sur les hôtes observés. |
| Délai | 650 ms par opération ICMP, TCP ou DNS, réglable de 100 à 3 000 ms. Windows gère le délai ARP. |
| DNS | Activé. Cache local et serveur du segment autorisé, si disponible. |
| Historique | `%LOCALAPPDATA%\RUX\inventory.sqlite3`, premier/dernier vu UTC par réseau et MAC. |
| Journal | `%LOCALAPPDATA%\RUX\rux.log`, rotation à 1 Mio, trois archives. |

Les constantes sont dans `core/config.py`. Le changement de plage, de carte ou d’options nécessite une nouvelle confirmation. Une route via une passerelle est exclue. Une disparition de carte ou un changement de sa configuration détecté pendant le scan interrompt le traitement. L’annulation laisse finir les appels réseau déjà engagés.

Le résultat reste disponible jusqu’au prochain scan lancé ou à la fermeture de RUX. SQLite conserve les dates des MAC connues. Une IP sans MAC reste propre à son scan. Les dates de la GUI utilisent l’heure locale, les exports utilisent UTC.

<h2 align="center">Exemple // Export JSON</h2>

Extrait **illustratif** du tableau `devices` d’un export JSON. `ports` contient les états des ports effectivement testés.

```json
{
  "ip": "192.168.42.10",
  "mac": "00:50:56:01:02:03",
  "hostname": "imprimante.lab",
  "vendor": "VMware, Inc.",
  "method": "ARP",
  "latency_ms": null,
  "first_seen": "2026-11-24T09:00:00.000Z",
  "last_seen": "2026-11-24T09:04:12.240Z",
  "ports": [{"port": 80, "state": "refused"}, {"port": 443, "state": "open"}]
}
```

Le bloc `scan` donne notamment la plage, l’interface, le nombre d’adresses traitées et le statut `completed`, `partial`, `cancelled` ou `failed`. Un CSV sans hôte contient quand même la ligne de résumé. Pour un scan annulé pendant l’identification, certains ports demandés peuvent rester non testés.

<h2 align="center">Utilisation // Autorisation et limites</h2>

Utilise RUX sur ton propre LAN ou avec l’autorisation de son responsable. L’accès physique ou Wi-Fi à un réseau ne confère pas, à lui seul, cette autorisation. RUX garde le périmètre sur l’interface choisie, adresse directement ses sondes et limite leur nombre. Les résultats et les logs sont locaux.

Un appareil en veille, sur un autre VLAN ou isolé par le point d’accès peut rester invisible. Un proxy ARP peut répondre pour plusieurs IP : le nombre d’IP observées ne garantit pas le nombre de machines physiques. Un refus TCP est distinct d’un délai expiré. Le nom DNS dépend des enregistrements disponibles, et le titulaire du préfixe MAC peut être un constructeur de carte réseau ou de matériel virtuel.

[Nmap](https://nmap.org/book/man.html) offre un inventaire plus configurable dans les périmètres où il est autorisé. [arp-scan](https://github.com/royhills/arp-scan) est spécialisé dans la découverte IPv4 par ARP sur le lien local. Ces outils restent indépendants de RUX.

<h2 align="center">Validation // Tests et plateformes</h2>

Les tests applicatifs utilisent un réseau simulé pour contrôler les réponses, les délais, les refus de route, les modifications de carte et l’annulation. Les tests Qt pilotent le vrai dialogue de consentement et la vraie table. Un test conditionnel Windows charge les DLL natives et énumère passivement les interfaces.

L’exécutable joint a été **assemblé hors Windows** à partir du bootloader graphique Windows x64 de PyInstaller, de CPython Windows 3.12.16 et des wheels Windows de Qt. Le format PE, les ressources de version et le contenu de l’archive interne ont été vérifiés. Sous Linux, 44 tests ont réussi, y compris les tests de la GUI réelle. Le 45e test est réservé aux DLL Windows. La recette de lancement et de découverte sur Windows 10/11 physiques ou virtualisés reste à effectuer. Le build natif standard, depuis les mêmes sources, suit `Build-RUX.cmd`.

Pour une recette sur un LAN autorisé, utilise un compte standard, vérifie l’interface, annule une première fois la confirmation, puis confirme un scan sur une petite tranche contenant un appareil connu. Contrôle son IP ou sa MAC, le filtre, les exports et la colonne des ports après activation explicite. Le bouton Annuler doit conserver un résultat partiel exportable.

<details>
<summary>Reproduire l’assemblage hors Windows</summary>

Cette méthode de distribution utilise les composants d’archive et le bootloader de PyInstaller. La commande `pyinstaller` standard construit pour son OS hôte. Pour l’assemblage spécifique, il faut un hôte Linux x64 avec CPython 3.12, uv, cpp et les outils GNU `x86_64-w64-mingw32-windres` et `x86_64-w64-mingw32-ld`. Utilise un dossier de travail distinct du répertoire des sources.

```bash
python3.12 -m venv .pack-venv
.pack-venv/bin/python -m pip install PyInstaller==6.22.3 pefile==2023.2.7 lief==1.0.0
uv python install -i "$PWD/win-runtime" cpython-3.12.16-windows-x86_64-none
runtime="$PWD/win-runtime/cpython-3.12.16-windows-x86_64-none"
.pack-venv/bin/python -m pip install --only-binary=:all: --platform win_amd64 --implementation cp --python-version 3.12 --abi cp312 --upgrade --target "$runtime/Lib/site-packages" PySide6-Essentials==6.10.3 PyInstaller==6.22.3 pywin32-ctypes pefile==2023.2.7
.pack-venv/bin/python /chemin/vers/sources/build/assemble_x64.py "$runtime" dist/RUX.exe
```

</details>

<h2 align="center">Références // Documentation technique</h2>

- [Adresses privées IPv4, RFC 1918](https://datatracker.ietf.org/doc/html/rfc1918)
- [Microsoft IP Helper, énumération des cartes](https://learn.microsoft.com/windows/win32/api/iphlpapi/nf-iphlpapi-getadaptersaddresses)
- [Microsoft GetBestRoute2](https://learn.microsoft.com/windows/win32/api/netioapi/nf-netioapi-getbestroute2)
- [Microsoft ResolveIpNetEntry2](https://learn.microsoft.com/windows/win32/api/netioapi/nf-netioapi-resolveipnetentry2)
- [Microsoft IcmpSendEcho2Ex](https://learn.microsoft.com/windows/win32/api/icmpapi/nf-icmpapi-icmpsendecho2ex)
- [Microsoft GetIpNetEntry2](https://learn.microsoft.com/windows/win32/api/netioapi/nf-netioapi-getipnetentry2)
- [Microsoft, options du résolveur DNS](https://learn.microsoft.com/windows/win32/dns/dns-constants)
- [IEEE Registration Authority](https://standards.ieee.org/products-programs/regauth/)
- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- [PyInstaller](https://pyinstaller.org/en/stable/)
