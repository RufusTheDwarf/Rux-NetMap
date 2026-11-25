# RUX NetMap · Référence technique

[Retour au README](../README.md) · [Code des skills](../skills/) · [Configuration](../core/config.py)

<h2 align="center">Cycle de vie // Du plan au rapport</h2>

La GUI prépare le plan avec la carte réseau, le CIDR, les options et le délai. La confirmation produit un consentement à usage unique. L’orchestrateur revalide le plan, limite le nombre de tâches en vol et diffuse les observations au thread Qt. Le poste local est reconnu directement. Pour un autre hôte, la découverte essaie ARP, puis ICMP si nécessaire. L’identification traite les hôtes observés, enregistre les enrichissements disponibles et transmet les résultats.

`Session.guard` contrôle l’adresse cible et la route locale sur l’interface choisie avant l’émission. Une disparition de carte ou une modification de sa configuration entraîne l’arrêt du scan. Une annulation laisse terminer les appels déjà partis et conserve les observations recueillies.

<h2 align="center">Agents // Répartition du travail</h2>

| Agent | Entrée | Sortie |
| :--- | :--- | :--- |
| [Orchestrateur](../agents/orchestrator.py) | Consentement et backend Windows | Un `Snapshot` avec statut, progression, observations et messages. |
| [Découverte](../agents/discovery.py) | Session et IPv4 | Un `Device` avec IP, méthode, dates et éventuellement MAC ou latence, ou `None`. |
| [Identification](../agents/identification.py) | Session, appareil observé et registre OUI | Un appareil enrichi avec les informations effectivement obtenues. |
| [Rapport](../agents/report.py) | `Snapshot`, format et chemin | Un rapport sérialisable ou un fichier CSV/JSON et le nombre d’hôtes écrits. |

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
