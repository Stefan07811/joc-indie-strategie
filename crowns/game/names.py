"""Names for the people born or raised to power during the campaign: first names by culture, and the
names of noble houses that can rise when a line dies out. (The people of 1402 have their real names.)"""

MALE = {
    "romanian": "Mircea Mihail Radu Dan Vlad Alexandru Petru Ștefan Bogdan Iliaș Roman Basarab Neagu Stanciu "
                "Dragomir Vlaicu Iuga Costea Oprea Nan".split(),
    "hungarian": "László István János Miklós Péter Pál György Mihály András Imre Lőrinc Tamás Benedek Dénes "
                 "Simon".split(),
    "german": "Albrecht Friedrich Heinrich Ludwig Ernst Leopold Wilhelm Ulrich Konrad Johann Otto Rudolf Georg "
              "Sigmund".split(),
    "czech": "Václav Jan Jiří Prokop Jindřich Oldřich Zikmund Petr Vilém Hynek Boček".split(),
    "polish": "Władysław Kazimierz Jan Bolesław Mikołaj Zbigniew Piotr Andrzej Stanisław Spytek".split(),
    "lithuanian": "Vytautas Kęstutis Žygimantas Mykolas Švitrigaila Jonas Butautas Kaributas".split(),
    "ruthenian": "Fedir Ivan Dmytro Vasyl Yurii Semen Oleksandr Andrii Mykhailo Ostafii".split(),
    "croatian": "Nikola Ivan Stjepan Martin Ivaniš Juraj Bartol Pavao Žigmund Frane".split(),
    "slovene": "Herman Friderik Ulrik Janez Andrej Jurij Mihael".split(),
    "slovak": "Ján Juraj Peter Matej Michal Ondrej".split(),
    "serbian": "Stefan Đurađ Lazar Vuk Grgur Nikola Marko Radoslav Branko Vukašin Uglješa Dragaš".split(),
    "bulgarian": "Ivan Asen Konstantin Mihail Shishman Fruzhin Stratsimir Georgi Petar".split(),
    "bosnian": "Stjepan Tvrtko Hrvoje Sandalj Vukac Pavle Radoslav Ostoja Vladislav Petar Radivoj".split(),
    "albanian": "Gjergj Gjon Pal Lekë Nikollë Tanush Progon Andrea Teodor Muriq Gjin Komnen Zakaria "
                "Dhimitër".split(),
    "greek": "Ioannes Manuel Theodoros Konstantinos Demetrios Thomas Andronikos Alexios Michael Georgios "
             "Nikephoros Isaakios".split(),
    "italian": "Carlo Leonardo Antonio Francesco Giacomo Pietro Niccolò Giovanni Marco Lorenzo Tommaso Filippo "
               "Centurione Dorino".split(),
    "french": "Jean Philippe Pierre Guillaume Louis Henri Charles Jacques Antoine".split(),
    "turkish": "Mehmed Murad Bayezid Musa Süleyman İsa Mustafa Orhan Ahmed Yakub İbrahim Hızır Osman İlyas "
               "Umur Hamza".split(),
    "tatar": "Edigu Tokhtamysh Shadi Pulad Jalal Kerim Ulugh Küchük Hacı Seyyid Nur Mansur".split(),
    "circassian": "Inal Tabula Kaytuk Beslan Temryuk Idar Kanshao Zhan".split(),
    "georgian": "Giorgi Alexandre Konstantine Bagrat Vakhtang Demetre Davit Levan Teimuraz".split(),
    "armenian": "Hovhannes Grigor Smbat Levon Hethum Kostandin Toros".split(),
    "arab": "Faraj Shaykh Barsbay Jaqmaq Inal Khushqadam Qaytbay Yashbak Tanibak Sudun".split(),
    "kurdish": "Hasan Ahmad Izz al-Din Sharaf Badr Mir Shams".split(),
}

FEMALE = {
    "romanian": "Maria Ana Elena Ruxandra Chiajna Despina Marina Stana Neacșa Anca".split(),
    "hungarian": "Erzsébet Katalin Anna Margit Ilona Orsolya Dorottya Borbála".split(),
    "german": "Elisabeth Anna Katharina Margarete Agnes Johanna Barbara Sophia".split(),
    "czech": "Anna Johana Kateřina Markéta Eliška Ludmila Žofie".split(),
    "polish": "Jadwiga Anna Elżbieta Zofia Katarzyna Małgorzata Barbara".split(),
    "lithuanian": "Sofija Ona Aldona Danutė Rimgailė Uliana Marija".split(),
    "ruthenian": "Olena Hanna Mariia Anastasiia Yevdokiia Sofiia".split(),
    "croatian": "Katarina Doroteja Jelena Ana Margareta Elizabeta".split(),
    "slovene": "Barbara Ana Katarina Margareta Veronika".split(),
    "slovak": "Anna Katarína Mária Žofia Alžbeta".split(),
    "serbian": "Jelena Mara Milica Olivera Katarina Jevdokija Teodora Jefimija".split(),
    "bulgarian": "Kera Tamara Desislava Irina Mara Elena".split(),
    "bosnian": "Jelena Katarina Kujava Doroteja Vitača Mara".split(),
    "albanian": "Helena Voisava Mamica Donika Mara Angelina Kiranna Rugina".split(),
    "greek": "Anna Helena Theodora Eirene Zoe Maria Sophia Eudokia Thomais".split(),
    "italian": "Maria Francesca Giovanna Caterina Lucia Valentina Bianca Agnese Chiara".split(),
    "french": "Jeanne Marie Isabelle Catherine Charlotte Blanche Marguerite".split(),
    "turkish": "Hatice Fatma Ayşe Selçuk Hafsa Devlet Emine Gülbahar".split(),
    "tatar": "Tulunbek Nur Canike Malika Sultan Aisha".split(),
    "circassian": "Goshanay Nalmes Satanay Zhanna Kuchenay".split(),
    "georgian": "Tamar Rusudan Nestan Gulkhan Elene Ketevan".split(),
    "armenian": "Mariun Zabel Fimi Shushan Anna".split(),
    "arab": "Fatima Khadija Zaynab Aisha Maryam Shirin".split(),
    "kurdish": "Fatma Gulistan Zeynep Hatun Ayşe".split(),
}

# Houses that can rise to power when a ruling line fails.
HOUSES = {
    "romanian": "Dănești Drăculești Craiovești Buzești Mușat Băleanu".split(),
    "hungarian": "Garai Hunyadi Kanizsai Cillei Újlaki Báthori Rozgonyi Perényi".split(),
    "german": "Wittelsbach Habsburg Hohenzollern Wettin Görz Liechtenstein".split(),
    "czech": "Rožmberk Poděbrady Šternberk Hradec Lipá".split(),
    "polish": "Tęczyński Melsztyński Szafraniec Oleśnicki Leliwa".split(),
    "lithuanian": "Goštautas Radvila Kęsgaila Olelkovič".split(),
    "ruthenian": "Ostrozky Zbaraski Chartoryski".split(),
    "croatian": "Nelipić Talovac Blagaj Kurjaković Zrinski".split(),
    "slovene": "Celje Auersperg Ortenburg".split(),
    "slovak": "Zápolya Rozgonyi Perényi".split(),
    "serbian": "Branković Mrnjavčević Dejanović Lazarević Crnojević".split(),
    "bulgarian": "Shishman Sratsimir Asen".split(),
    "bosnian": "Kotromanić Kosača Pavlović Hrvatinić Dinjičić".split(),
    "albanian": "Kastrioti Dukagjini Arianiti Thopia Muzaka Zenebishi Dushmani Spani Balšić".split(),
    "greek": "Kantakouzenos Palaiologos Asanes Laskaris Notaras Philanthropenos Rhaoul".split(),
    "italian": "Tocco Acciaioli Zaccaria Gattilusio Crispo Giustiniani Malatesta Orsini Colonna".split(),
    "french": "Lusignan Ibelin Naillac Brienne".split(),
    "turkish": "Osman Candaroğlu Karamanoğlu Evrenos Mihaloğlu Turahan Timurtaş".split(),
    "tatar": "Giray Shirin Barin Mangit".split(),
    "circassian": "Inal Kaytuk Bekmurza".split(),
    "georgian": "Bagrationi Dadiani Jaqeli Gurieli".split(),
    "armenian": "Hethumid Rubenid Artsruni".split(),
    "arab": "Barquq Mu'ayyad Ashrafi".split(),
    "kurdish": "Bohtan Hakkari Ardalan".split(),
}


def pick(table, culture, rng):
    names = table.get(culture) or table["italian"]
    return rng.choice(names)
