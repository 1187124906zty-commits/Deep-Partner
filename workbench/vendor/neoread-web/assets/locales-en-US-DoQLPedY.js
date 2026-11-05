const r=`<?xml version="1.0" encoding="utf-8"?>\r
<locale xmlns="http://purl.org/net/xbiblio/csl" version="1.0" xml:lang="en-US">\r
  <!-- The abbreviations in this file follow the recommendations of The Chicago Manual of Style, 18th ed. (2024), sec. 10.48 (cited hereafter as CMOS), unless stated otherwise. -->\r
  <!-- Additional abbreviations are from:\r
        1. Oxford Dictionary for Writers and Editors (2000), https://archive.org/details/oxfordstylemanua0000unse (cited hereafter as ODWE): reference has also been made to the New Oxford Dictionary for Writers and Editors (NODWE), but periods must be added to contractions in these later editions to reflect US English usage\r
        2. Oxford Dictionary of Abbreviations (2011), https://doi.org/10.1093/acref/9780199698295.001.0001 (cited hereafter as ODA)\r
  -->\r
  <info>\r
    <translator>\r
      <name>Andrew Dunning</name>\r
      <uri>https://orcid.org/0000-0003-0464-5036</uri>\r
    </translator>\r
    <translator>\r
      <name>Sebastian Karcher</name>\r
      <uri>https://orcid.org/0000-0001-8249-7388</uri>\r
    </translator>\r
    <translator>\r
      <name>Rintze M. Zelle</name>\r
      <uri>https://orcid.org/0000-0003-1779-8883</uri>\r
    </translator>\r
    <translator>\r
      <name>Denis Meier</name>\r
    </translator>\r
    <translator>\r
      <name>Brenton M. Wiernik</name>\r
      <uri>https://orcid.org/0000-0001-9560-6336</uri>\r
    </translator>\r
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>\r
    <updated>2026-01-10T00:00:00+00:00</updated>\r
  </info>\r
  <style-options punctuation-in-quote="true"/>\r
  <date form="text">\r
    <date-part name="month" suffix=" "/>\r
    <date-part name="day" suffix=", "/>\r
    <date-part name="year"/>\r
  </date>\r
  <date form="numeric">\r
    <date-part name="month" form="numeric-leading-zeros" suffix="/"/>\r
    <date-part name="day" form="numeric-leading-zeros" suffix="/"/>\r
    <date-part name="year"/>\r
  </date>\r
  <terms>\r
    <!-- LONG GENERAL TERMS -->\r
    <term name="accessed">accessed</term>\r
    <term name="advance-online-publication">advance online publication</term>\r
    <term name="album">album</term>\r
    <term name="and">and</term>\r
    <term name="and others">and others</term>\r
    <term name="anonymous">anonymous</term>\r
    <term name="at">at</term>\r
    <term name="audio-recording">audio recording</term>\r
    <term name="available at">available at</term>\r
    <term name="by">by</term>\r
    <term name="circa">circa</term>\r
    <term name="cited">cited</term>\r
    <term name="et-al">et al.</term>\r
    <term name="film">film</term>\r
    <term name="forthcoming">forthcoming</term>\r
    <term name="from">from</term>\r
    <term name="henceforth">henceforth</term>\r
    <term name="ibid">ibid.</term>\r
    <term name="in">in</term>\r
    <term name="in press">in press</term>\r
    <term name="internet">internet</term>\r
    <term name="letter">letter</term>\r
    <term name="loc-cit">loc. cit.</term> <!-- like ibid., the abbreviated form is the regular form  -->\r
    <term name="no date">no date</term>\r
    <term name="no-place">no place</term>\r
    <term name="no-publisher">no publisher</term>\r
    <term name="on">on</term>\r
    <term name="online">online</term>\r
    <term name="op-cit">op. cit.</term> <!-- like ibid., the abbreviated form is the regular form  -->\r
    <term name="original-work-published">original work published</term>\r
    <term name="personal-communication">personal communication</term>\r
    <term name="podcast">podcast</term>\r
    <term name="podcast-episode">podcast episode</term>\r
    <term name="preprint">preprint</term>\r
    <term name="presented at">presented at the</term>\r
    <term name="radio-broadcast">radio broadcast</term>\r
    <term name="radio-series">radio series</term>\r
    <term name="radio-series-episode">radio series episode</term>\r
    <term name="reference">\r
      <single>reference</single>\r
      <multiple>references</multiple>\r
    </term>\r
    <term name="retrieved">retrieved</term>\r
    <term name="review-of">review of</term>\r
    <term name="scale">scale</term>\r
    <term name="special-issue">special issue</term>\r
    <term name="special-section">special section</term>\r
    <term name="television-broadcast">television broadcast</term>\r
    <term name="television-series">television series</term>\r
    <term name="television-series-episode">television series episode</term>\r
    <term name="video">video</term>\r
    <term name="working-paper">working paper</term>\r
\r
    <!-- SHORT GENERAL TERMS -->\r
    <!-- Omitted short forms: accessed, album, and (symbol), and others, at (symbol), forthcoming, henceforth, ibid, in, in press, internet, loc-cit, on, online, op-cit, podcast, preprint, presented at -->\r
    <term name="advance-online-publication" form="short">adv. online pub.</term> <!-- ODA -->\r
    <term name="anonymous" form="short">anon.</term>\r
    <term name="audio-recording" form="short">au. rec.</term> <!-- ODA -->\r
    <term name="available at" form="short">avail. at</term> <!-- ODA -->\r
    <term name="circa" form="short">c.</term>\r
    <!-- CMOS 10.48 recommends "ca." for "circa" but also allows "c.", which CSL has used historically -->\r
    <term name="cited" form="short">cit.</term> <!-- ODA -->\r
    <term name="film" form="short">flm.</term> <!-- ODA -->\r
    <term name="from" form="short">fr.</term>\r
    <term name="letter" form="short">let.</term> <!-- ODA -->\r
    <term name="no date" form="short">n.d.</term>\r
    <term name="no-place" form="short">n.p.</term>\r
    <term name="no-publisher" form="short">n.p.</term>\r
    <term name="original-work-published" form="short">orig. pub.</term> <!-- Oxford Guide to Style -->\r
    <term name="personal-communication" form="short">pers. comm.</term>\r
    <term name="podcast-episode" form="short">podcast ep.</term>\r
    <term name="radio-broadcast" form="short">radio bdcst.</term> <!-- ODA -->\r
    <term name="radio-series" form="short">radio ser.</term> <!-- ODA -->\r
    <term name="radio-series-episode" form="short">radio ser. ep.</term> <!-- ODA -->\r
    <term name="reference" form="short">\r
      <single>ref.</single>\r
      <multiple>refs.</multiple>\r
    </term>\r
    <term name="retrieved" form="short">rtvd.</term> <!-- ODA -->\r
    <term name="review-of" form="short">rev. of</term>\r
    <term name="scale" form="short">sc.</term> <!-- ODA -->\r
    <term name="special-issue" form="short">spec. iss.</term> <!-- ODA -->\r
    <term name="special-section" form="short">spec. sec.</term> <!-- ODA/CMOS -->\r
    <term name="television-broadcast" form="short">TV bdcst.</term> <!-- ODA -->\r
    <term name="television-series" form="short">TV ser.</term> <!-- ODA -->\r
    <term name="television-series-episode" form="short">TV ser. ep.</term> <!-- ODA -->\r
    <term name="video" form="short">vid.</term> <!-- ODA -->\r
    <term name="working-paper" form="short">wkg. paper</term> <!-- ODA -->\r
\r
    <!-- SYMBOLIC GENERAL FORMS -->\r
    <term name="and" form="symbol">&amp;</term>\r
    <term name="at" form="symbol">@</term>\r
\r
    <!-- LONG ITEM TYPE FORMS -->\r
    <term name="article">preprint</term>\r
    <term name="article-journal">journal article</term>\r
    <term name="article-magazine">magazine article</term>\r
    <term name="article-newspaper">newspaper article</term>\r
    <term name="bill">bill</term>\r
    <!-- book is in the list of locator terms -->\r
    <term name="broadcast">broadcast</term>\r
    <!-- chapter is in the list of locator terms -->\r
    <term name="classic">classical work</term>\r
    <term name="collection">archival collection</term>\r
    <term name="dataset">dataset</term>\r
    <term name="document">document</term>\r
    <term name="entry">entry</term>\r
    <term name="entry-dictionary">dictionary entry</term>\r
    <term name="entry-encyclopedia">encyclopedia entry</term>\r
    <term name="event">event</term>\r
    <!-- figure is in the list of locator terms -->\r
    <term name="graphic">graphic</term>\r
    <term name="hearing">hearing</term>\r
    <term name="interview">interview</term>\r
    <term name="legal_case">legal case</term>\r
    <term name="legislation">legislation</term>\r
    <term name="manuscript">manuscript</term>\r
    <term name="map">map</term>\r
    <term name="motion_picture">video recording</term>\r
    <term name="musical_score">musical score</term>\r
    <term name="pamphlet">pamphlet</term>\r
    <term name="paper-conference">conference paper</term>\r
    <term name="patent">patent</term>\r
    <term name="performance">performance</term>\r
    <term name="periodical">periodical</term>\r
    <term name="personal_communication">personal communication</term>\r
    <term name="post">post</term>\r
    <term name="post-weblog">blog post</term>\r
    <term name="regulation">regulation</term>\r
    <term name="report">report</term>\r
    <term name="review">review</term>\r
    <term name="review-book">book review</term>\r
    <term name="software">software</term>\r
    <term name="song">audio recording</term>\r
    <term name="speech">presentation</term>\r
    <term name="standard">standard</term>\r
    <term name="thesis">thesis</term>\r
    <term name="treaty">treaty</term>\r
    <term name="webpage">webpage</term>\r
\r
    <!-- SHORT ITEM TYPE FORMS -->\r
    <!-- Omitted short forms: article, bill, entry, event, hearing, map, periodical, speech, treaty -->\r
    <term name="article-journal" form="short">jour. art.</term> <!-- ODWE -->\r
    <term name="article-magazine" form="short">mag. art.</term> <!-- ODWE -->\r
    <term name="article-newspaper" form="short">newspaper art.</term>\r
    <term name="broadcast" form="short">bdcst.</term> <!-- ODA -->\r
    <!-- book is in the list of locator terms -->\r
    <!-- chapter is in the list of locator terms -->\r
    <term name="classic" form="short">class. wk.</term> <!-- ODWE -->\r
    <term name="collection" form="short">arch. coll.</term> <!-- ODA -->\r
    <term name="document" form="short">doc.</term>\r
    <term name="entry-dictionary" form="short">dict. entry</term>\r
    <term name="entry-encyclopedia" form="short">ency. entry</term>\r
    <!-- figure is in the list of locator terms -->\r
    <term name="graphic" form="short">gr.</term> <!-- ODA -->\r
    <term name="interview" form="short">int.</term> <!-- ODA -->\r
    <term name="legal_case" form="short">leg. case</term> <!-- ODA -->\r
    <term name="legislation" form="short">legis.</term> <!-- ODA -->\r
    <term name="manuscript" form="short">\r
      <single>MS</single>\r
      <multiple>MSS</multiple>\r
    </term>\r
    <term name="motion_picture" form="short">vid. rec.</term> <!-- ODA -->\r
    <term name="musical_score" form="short">mus. score</term> <!-- ODWE -->\r
    <term name="pamphlet" form="short">pam.</term> <!-- ODWE -->\r
    <term name="paper-conference" form="short">conf. paper</term> <!-- ODA -->\r
    <term name="patent" form="short">pat.</term> <!-- ODWE -->\r
    <term name="performance" form="short">prfm.</term> <!-- ODA -->\r
    <term name="personal_communication" form="short">pers. comm.</term>\r
    <term name="regulation" form="short">reg.</term> <!-- ODA -->\r
    <term name="report" form="short">rep.</term> <!-- ODWE -->\r
    <term name="review" form="short">rev.</term>\r
    <term name="review-book" form="short">bk. rev.</term>\r
    <term name="software" form="short">sftw.</term> <!-- ODA -->\r
    <term name="song" form="short">au. rec.</term> <!-- ODA -->\r
    <term name="standard" form="short">std.</term> <!-- ODA -->\r
    <term name="thesis" form="short">thes.</term> <!-- ODA -->\r
    <term name="webpage" form="short">webpg.</term> <!-- ODA -->\r
\r
    <!-- LONG VERB ITEM TYPE FORMS -->\r
    <!-- Only where applicable -->\r
    <term name="hearing" form="verb">testimony of</term>\r
    <term name="review" form="verb">review of</term>\r
    <term name="review-book" form="verb">review of the book</term>\r
\r
    <!-- SHORT VERB ITEM TYPE FORMS -->\r
    <!-- Only where applicable -->\r
    <term name="hearing" form="verb-short">test. of</term> <!-- ODA -->\r
    <term name="review" form="verb-short">rev. of</term>\r
    <term name="review-book" form="verb-short">rev. of the bk.</term>\r
\r
    <!-- HISTORICAL ERA TERMS -->\r
    <term name="ad"> AD</term>\r
    <term name="bc"> BC</term>\r
    <term name="bce"> BCE</term>\r
    <term name="ce"> CE</term>\r
\r
    <!-- PUNCTUATION -->\r
    <term name="open-quote">“</term>\r
    <term name="close-quote">”</term>\r
    <term name="open-inner-quote">‘</term>\r
    <term name="close-inner-quote">’</term>\r
    <term name="page-range-delimiter">–</term>\r
    <term name="colon">:</term>\r
    <term name="comma">,</term>\r
    <term name="semicolon">;</term>\r
\r
    <!-- ORDINALS -->\r
    <term name="ordinal">th</term>\r
    <term name="ordinal-01">st</term>\r
    <term name="ordinal-02">nd</term>\r
    <term name="ordinal-03">rd</term>\r
    <term name="ordinal-11">th</term>\r
    <term name="ordinal-12">th</term>\r
    <term name="ordinal-13">th</term>\r
\r
    <!-- LONG ORDINALS -->\r
    <term name="long-ordinal-01">first</term>\r
    <term name="long-ordinal-02">second</term>\r
    <term name="long-ordinal-03">third</term>\r
    <term name="long-ordinal-04">fourth</term>\r
    <term name="long-ordinal-05">fifth</term>\r
    <term name="long-ordinal-06">sixth</term>\r
    <term name="long-ordinal-07">seventh</term>\r
    <term name="long-ordinal-08">eighth</term>\r
    <term name="long-ordinal-09">ninth</term>\r
    <term name="long-ordinal-10">tenth</term>\r
\r
    <!-- LONG LOCATOR FORMS -->\r
    <term name="act">\r
      <single>act</single>\r
      <multiple>acts</multiple>\r
    </term>\r
    <term name="appendix">\r
      <single>appendix</single>\r
      <multiple>appendices</multiple>\r
    </term>\r
    <term name="article-locator">\r
      <single>article</single>\r
      <multiple>articles</multiple>\r
    </term>\r
    <term name="book">\r
      <single>book</single>\r
      <multiple>books</multiple>\r
    </term>\r
    <term name="canon">\r
      <single>canon</single>\r
      <multiple>canons</multiple>\r
    </term>\r
    <term name="chapter">\r
      <single>chapter</single>\r
      <multiple>chapters</multiple>\r
    </term>\r
    <term name="column">\r
      <single>column</single>\r
      <multiple>columns</multiple>\r
    </term>\r
    <term name="elocation">\r
      <single>location</single>\r
      <multiple>locations</multiple>\r
    </term>\r
    <term name="equation">\r
      <single>equation</single>\r
      <multiple>equations</multiple>\r
    </term>\r
    <term name="figure">\r
      <single>figure</single>\r
      <multiple>figures</multiple>\r
    </term>\r
    <term name="folio">\r
      <single>folio</single>\r
      <multiple>folios</multiple>\r
    </term>\r
    <term name="issue">\r
      <single>issue</single>\r
      <multiple>issues</multiple>\r
    </term>\r
    <term name="line">\r
      <single>line</single>\r
      <multiple>lines</multiple>\r
    </term>\r
    <term name="note">\r
      <single>note</single>\r
      <multiple>notes</multiple>\r
    </term>\r
    <term name="opus">\r
      <single>opus</single>\r
      <multiple>opera</multiple>\r
    </term>\r
    <term name="page">\r
      <single>page</single>\r
      <multiple>pages</multiple>\r
    </term>\r
    <term name="paragraph">\r
      <single>paragraph</single>\r
      <multiple>paragraphs</multiple>\r
    </term>\r
    <term name="part">\r
      <single>part</single>\r
      <multiple>parts</multiple>\r
    </term>\r
    <term name="rule">\r
      <single>rule</single>\r
      <multiple>rules</multiple>\r
    </term>\r
    <term name="scene">\r
      <single>scene</single>\r
      <multiple>scenes</multiple>\r
    </term>\r
    <term name="section">\r
      <single>section</single>\r
      <multiple>sections</multiple>\r
    </term>\r
    <term name="sub-verbo">\r
      <single>sub verbo</single>\r
      <multiple>sub verbis</multiple>\r
    </term>\r
    <term name="supplement">\r
      <single>supplement</single>\r
      <multiple>supplements</multiple>\r
    </term>\r
    <term name="table">\r
      <single>table</single>\r
      <multiple>tables</multiple>\r
    </term>\r
    <!-- A timestamp is a composite of hours, minutes, etc. and therefore has no default label. -->\r
    <term name="timestamp"/>\r
    <term name="title-locator">\r
      <single>title</single>\r
      <multiple>titles</multiple>\r
    </term>\r
    <term name="verse">\r
      <single>verse</single>\r
      <multiple>verses</multiple>\r
    </term>\r
    <term name="volume">\r
      <single>volume</single>\r
      <multiple>volumes</multiple>\r
    </term>\r
\r
    <!-- SHORT LOCATOR FORMS -->\r
    <!-- Omitted short forms: act, timestamp -->\r
    <term name="appendix" form="short">\r
      <single>app.</single>\r
      <multiple>apps.</multiple>\r
    </term>\r
    <term name="article-locator" form="short">\r
      <single>art.</single>\r
      <multiple>arts.</multiple>\r
    </term>\r
    <term name="book" form="short">\r
      <single>bk.</single>\r
      <multiple>bks.</multiple>\r
    </term>\r
    <term name="canon" form="short">\r
      <!-- Oxford Dictionary for Writers and Editors -->\r
      <single>can.</single>\r
      <multiple>cann.</multiple>\r
    </term>\r
    <term name="chapter" form="short">\r
      <single>chap.</single>\r
      <multiple>chaps.</multiple>\r
    </term>\r
    <term name="column" form="short">\r
      <single>col.</single>\r
      <multiple>cols.</multiple>\r
    </term>\r
    <term name="elocation" form="short">\r
      <single>loc.</single>\r
      <multiple>locs.</multiple>\r
    </term>\r
    <term name="equation" form="short">\r
      <single>eq.</single>\r
      <multiple>eqq.</multiple>\r
    </term>\r
    <term name="figure" form="short">\r
      <single>fig.</single>\r
      <multiple>figs.</multiple>\r
    </term>\r
    <term name="folio" form="short">\r
      <single>fol.</single>\r
      <multiple>fols.</multiple>\r
    </term>\r
    <term name="issue" form="short">\r
      <single>no.</single>\r
      <multiple>nos.</multiple>\r
    </term>\r
    <term name="line" form="short">\r
      <single>l.</single>\r
      <multiple>ll.</multiple>\r
    </term>\r
    <term name="note" form="short">\r
      <single>n.</single>\r
      <multiple>nn.</multiple>\r
    </term>\r
    <term name="opus" form="short">\r
      <single>op.</single>\r
      <multiple>opp.</multiple>\r
    </term>\r
    <term name="page" form="short">\r
      <single>p.</single>\r
      <multiple>pp.</multiple>\r
    </term>\r
    <term name="paragraph" form="short">\r
      <single>para.</single>\r
      <multiple>paras.</multiple>\r
    </term>\r
    <term name="part" form="short">\r
      <single>pt.</single>\r
      <multiple>pts.</multiple>\r
    </term>\r
    <term name="rule" form="short">\r
      <!-- legal abbreviations in the Oxford Guide to Style, sec. 13.2.1 -->\r
      <single>r.</single>\r
      <multiple>rr.</multiple>\r
    </term>\r
    <term name="scene" form="short">\r
      <single>sc.</single>\r
      <multiple>scs.</multiple>\r
    </term>\r
    <term name="section" form="short">\r
      <single>sec.</single>\r
      <multiple>secs.</multiple>\r
    </term>\r
    <term name="sub-verbo" form="short">\r
      <single>s.v.</single>\r
      <multiple>s.vv.</multiple>\r
    </term>\r
    <term name="supplement" form="short">\r
      <single>supp.</single>\r
      <multiple>supps.</multiple>\r
    </term>\r
    <term name="table" form="short">\r
      <!-- Oxford Dictionary of Abbreviations -->\r
      <single>tbl.</single>\r
      <multiple>tbls.</multiple>\r
    </term>\r
    <term name="title-locator" form="short">\r
      <!-- Oxford Dictionary for Writers and Editors -->\r
      <single>tit.</single>\r
      <multiple>titt.</multiple>\r
    </term>\r
    <term name="verse" form="short">\r
      <single>v.</single>\r
      <multiple>vv.</multiple>\r
    </term>\r
    <term name="volume" form="short">\r
      <single>vol.</single>\r
      <multiple>vols.</multiple>\r
    </term>\r
\r
    <!-- SYMBOLIC LOCATOR FORMS -->\r
    <term name="chapter" form="symbol">\r
      <!-- caput/capita, esp. in legal works; cf. CMOS 14.196 -->\r
      <single>c.</single>\r
      <multiple>cc.</multiple>\r
    </term>\r
    <term name="paragraph" form="symbol">\r
      <single>¶</single>\r
      <multiple>¶¶</multiple>\r
    </term>\r
    <term name="section" form="symbol">\r
      <single>§</single>\r
      <multiple>§§</multiple>\r
    </term>\r
\r
    <!-- LONG NUMBER VARIABLE FORMS -->\r
    <term name="chapter-number">\r
      <single>chapter</single>\r
      <multiple>chapters</multiple>\r
    </term>\r
    <term name="citation-number">\r
      <single>citation</single>\r
      <multiple>citations</multiple>\r
    </term>\r
    <term name="collection-number">\r
      <single>number</single>\r
      <multiple>numbers</multiple>\r
    </term>\r
    <term name="edition">\r
      <single>edition</single>\r
      <multiple>editions</multiple>\r
    </term>\r
    <term name="first-reference-note-number">\r
      <single>note</single>\r
      <multiple>notes</multiple>\r
    </term>\r
    <term name="number">\r
      <single>number</single>\r
      <multiple>numbers</multiple>\r
    </term>\r
    <term name="number-of-pages">\r
      <single>page</single>\r
      <multiple>pages</multiple>\r
    </term>\r
    <term name="number-of-volumes">\r
      <single>volume</single>\r
      <multiple>volumes</multiple>\r
    </term>\r
    <term name="page-first">\r
      <single>page</single>\r
      <multiple>pages</multiple>\r
    </term>\r
    <term name="printing">\r
      <single>printing</single>\r
      <multiple>printings</multiple>\r
    </term>\r
    <term name="version">\r
      <single>version</single>\r
      <multiple>versions</multiple>\r
    </term>\r
\r
    <!-- SHORT NUMBER VARIABLE FORMS -->\r
    <term name="chapter-number" form="short">\r
      <single>chap.</single>\r
      <multiple>chaps.</multiple>\r
    </term>\r
    <term name="citation-number" form="short">\r
      <single>cit.</single>\r
      <multiple>cits.</multiple>\r
    </term>\r
    <term name="collection-number" form="short">\r
      <single>no.</single>\r
      <multiple>nos.</multiple>\r
    </term>\r
    <term name="edition" form="short">\r
      <single>ed.</single>\r
      <multiple>eds.</multiple>\r
    </term>\r
    <term name="first-reference-note-number" form="short">\r
      <single>n.</single>\r
      <multiple>nn.</multiple>\r
    </term>\r
    <term name="number" form="short">\r
      <single>no.</single>\r
      <multiple>nos.</multiple>\r
    </term>\r
    <term name="number-of-pages" form="short">\r
      <single>p.</single>\r
      <multiple>pp.</multiple>\r
    </term>\r
    <term name="number-of-volumes" form="short">\r
      <single>vol.</single>\r
      <multiple>vols.</multiple>\r
    </term>\r
    <term name="page-first" form="short">\r
      <single>p.</single>\r
      <multiple>pp.</multiple>\r
    </term>\r
    <term name="printing" form="short">\r
      <!-- Oxford Dictionary for Writers and Editors -->\r
      <single>ptg.</single>\r
      <multiple>ptgs.</multiple>\r
    </term>\r
    <term name="version" form="short">v.</term> <!-- no plural -->\r
\r
    <!-- LONG ROLE FORMS -->\r
    <term name="author"/> <!-- generally blank -->\r
    <term name="chair">\r
      <single>chair</single>\r
      <multiple>chairs</multiple>\r
    </term>\r
    <term name="collection-editor">\r
      <single>editor</single>\r
      <multiple>editors</multiple>\r
    </term>\r
    <term name="compiler">\r
      <single>compiler</single>\r
      <multiple>compilers</multiple>\r
    </term>\r
    <term name="composer"/> <!-- generally blank -->\r
    <term name="container-author"/> <!-- generally blank -->\r
    <term name="contributor">\r
      <single>contributor</single>\r
      <multiple>contributors</multiple>\r
    </term>\r
    <term name="curator">\r
      <single>curator</single>\r
      <multiple>curators</multiple>\r
    </term>\r
    <term name="director">\r
      <single>director</single>\r
      <multiple>directors</multiple>\r
    </term>\r
    <term name="editor">\r
      <single>editor</single>\r
      <multiple>editors</multiple>\r
    </term>\r
    <term name="editor-translator">\r
      <single>editor &amp; translator</single>\r
      <multiple>editors &amp; translators</multiple>\r
    </term>\r
    <term name="editortranslator">\r
      <single>editor &amp; translator</single>\r
      <multiple>editors &amp; translators</multiple>\r
    </term>\r
    <term name="editorial-director">\r
      <single>editor</single>\r
      <multiple>editors</multiple>\r
    </term>\r
    <term name="executive-producer">\r
      <single>executive producer</single>\r
      <multiple>executive producers</multiple>\r
    </term>\r
    <term name="guest">\r
      <single>guest</single>\r
      <multiple>guests</multiple>\r
    </term>\r
    <term name="host">\r
      <single>host</single>\r
      <multiple>hosts</multiple>\r
    </term>\r
    <term name="illustrator">\r
      <single>illustrator</single>\r
      <multiple>illustrators</multiple>\r
    </term>\r
    <term name="interviewer"/> <!-- generally blank -->\r
    <term name="narrator">\r
      <single>narrator</single>\r
      <multiple>narrators</multiple>\r
    </term>\r
    <term name="organizer">\r
      <single>organizer</single>\r
      <multiple>organizers</multiple>\r
    </term>\r
    <term name="original-author"/> <!-- generally blank -->\r
    <term name="performer">\r
      <single>performer</single>\r
      <multiple>performers</multiple>\r
    </term>\r
    <term name="producer">\r
      <single>producer</single>\r
      <multiple>producers</multiple>\r
    </term>\r
    <term name="recipient"/> <!-- generally blank -->\r
    <term name="reviewed-author"/> <!-- generally blank -->\r
    <term name="script-writer">\r
      <single>writer</single>\r
      <multiple>writers</multiple>\r
    </term>\r
    <term name="series-creator">\r
      <single>series creator</single>\r
      <multiple>series creators</multiple>\r
    </term>\r
    <term name="translator">\r
      <single>translator</single>\r
      <multiple>translators</multiple>\r
    </term>\r
\r
    <!-- SHORT ROLE FORMS -->\r
    <!-- Omitted roles:\r
         author, chair, composer, container-author, guest, host, interviewer, original-author, recipient, reviewed-author\r
    -->\r
    <term name="collection-editor" form="short">\r
      <single>ed.</single>\r
      <multiple>eds.</multiple>\r
    </term>\r
    <term name="compiler" form="short">\r
      <single>comp.</single>\r
      <multiple>comps.</multiple>\r
    </term>\r
    <term name="contributor" form="short">\r
      <!-- Oxford Dictionary of Abbreviations -->\r
      <single>contrib.</single>\r
      <multiple>contribs.</multiple>\r
    </term>\r
    <term name="curator" form="short">\r
      <!-- Oxford Art Online <https://www.oxfordartonline.com/page/1661> -->\r
      <single>cur.</single>\r
      <multiple>curs.</multiple>\r
    </term>\r
    <term name="director" form="short">\r
      <single>dir.</single>\r
      <multiple>dirs.</multiple>\r
    </term>\r
    <term name="editor" form="short">\r
      <single>ed.</single>\r
      <multiple>eds.</multiple>\r
    </term>\r
    <term name="editor-translator" form="short">\r
      <single>ed. &amp; trans.</single>\r
      <multiple>eds. &amp; trans.</multiple>\r
    </term>\r
    <term name="editortranslator" form="short">\r
      <single>ed. &amp; trans.</single>\r
      <multiple>eds. &amp; trans.</multiple>\r
    </term>\r
    <term name="editorial-director" form="short">\r
      <single>ed.</single>\r
      <multiple>eds.</multiple>\r
    </term>\r
    <term name="executive-producer" form="short">\r
      <!-- Oxford Dictionary of Abbreviations -->\r
      <single>exec. prod.</single>\r
      <multiple>exec. prods.</multiple>\r
    </term>\r
    <term name="illustrator" form="short">\r
      <single>ill.</single>\r
      <multiple>ills.</multiple>\r
    </term>\r
    <term name="narrator" form="short">\r
      <!-- Oxford Dictionary of Abbreviations -->\r
      <single>narr.</single>\r
      <multiple>narrs.</multiple>\r
    </term>\r
    <term name="organizer" form="short">\r
      <!-- possibly misleading: Oxford Dictionary of Abbreviations only defines this as organization or organized -->\r
      <single>org.</single>\r
      <multiple>orgs.</multiple>\r
    </term>\r
    <term name="performer" form="short">\r
      <!-- Oxford Dictionary of Abbreviations -->\r
      <single>perf.</single>\r
      <multiple>perfs.</multiple>\r
    </term>\r
    <term name="producer" form="short">\r
      <!-- Oxford Dictionary of Abbreviations -->\r
      <single>prod.</single>\r
      <multiple>prods.</multiple>\r
    </term>\r
    <term name="script-writer" form="short">\r
      <!-- Oxford Dictionary of Abbreviations -->\r
      <single>wrtr.</single>\r
      <multiple>wrtrs.</multiple>\r
    </term>\r
    <term name="series-creator" form="short">\r
      <single>ser. creator</single>\r
      <multiple>ser. creators</multiple>\r
    </term>\r
    <term name="translator" form="short">trans.</term> <!-- no plural -->\r
\r
    <!-- VERB ROLE FORMS -->\r
    <term name="chair" form="verb">chaired by</term>\r
    <term name="collection-editor" form="verb">edited by</term>\r
    <term name="compiler" form="verb">compiled by</term>\r
    <term name="composer" form="verb">composed by</term>\r
    <term name="container-author" form="verb">by</term>\r
    <term name="contributor" form="verb">with</term>\r
    <term name="curator" form="verb">curated by</term>\r
    <term name="director" form="verb">directed by</term>\r
    <term name="editor" form="verb">edited by</term>\r
    <term name="editor-translator" form="verb">edited &amp; translated by</term>\r
    <term name="editortranslator" form="verb">edited &amp; translated by</term>\r
    <term name="editorial-director" form="verb">edited by</term>\r
    <term name="executive-producer" form="verb">executive produced by</term>\r
    <term form="verb" name="guest">\r
      <single>with guest</single>\r
      <multiple>with guests</multiple>\r
    </term>\r
    <term name="host" form="verb">hosted by</term>\r
    <term name="illustrator" form="verb">illustrated by</term>\r
    <term name="interviewer" form="verb">interview by</term>\r
    <term name="narrator" form="verb">narrated by</term>\r
    <term name="organizer" form="verb">organized by</term>\r
    <term name="original-author" form="verb">by</term>\r
    <term name="performer" form="verb">performed by</term>\r
    <term name="producer" form="verb">produced by</term>\r
    <term name="recipient" form="verb">to</term>\r
    <term name="reviewed-author" form="verb">by</term>\r
    <term name="script-writer" form="verb">written by</term>\r
    <term name="series-creator" form="verb">created by</term>\r
    <term name="translator" form="verb">translated by</term>\r
\r
    <!-- SHORT VERB ROLE FORMS -->\r
    <!-- Omitted roles:\r
         author, chair, container-author, contributor, guest, host, interviewer, original-author, recipient, reviewed-author, series-creator\r
    -->\r
    <term name="collection-editor" form="verb-short">ed. by</term>\r
    <term name="compiler" form="verb-short">comp. by</term>\r
    <term name="composer" form="verb-short">comp. by</term> <!-- ODWE -->\r
    <term name="curator" form="verb-short">cur. by</term> <!-- Oxford Art Online -->\r
    <term name="director" form="verb-short">dir. by</term>\r
    <term name="editor" form="verb-short">ed. by</term>\r
    <term name="editor-translator" form="verb-short">ed. &amp; trans. by</term>\r
    <term name="editortranslator" form="verb-short">ed. &amp; trans. by</term>\r
    <term name="editorial-director" form="verb-short">ed. by</term>\r
    <term name="executive-producer" form="verb-short">exec. prod. by</term> <!-- ODA -->\r
    <term name="illustrator" form="verb-short">ill. by</term>\r
    <term name="narrator" form="verb-short">narr. by</term> <!-- ODA -->\r
    <term name="organizer" form="verb-short">org. by</term> <!-- ODA -->\r
    <term name="performer" form="verb-short">perf. by</term> <!-- ODA -->\r
    <term name="producer" form="verb-short">prod. by</term> <!-- ODA -->\r
    <term name="script-writer" form="verb-short">writ. by</term> <!-- ODA -->\r
    <term name="translator" form="verb-short">trans. by</term>\r
\r
    <!-- LONG MONTH FORMS -->\r
    <term name="month-01">January</term>\r
    <term name="month-02">February</term>\r
    <term name="month-03">March</term>\r
    <term name="month-04">April</term>\r
    <term name="month-05">May</term>\r
    <term name="month-06">June</term>\r
    <term name="month-07">July</term>\r
    <term name="month-08">August</term>\r
    <term name="month-09">September</term>\r
    <term name="month-10">October</term>\r
    <term name="month-11">November</term>\r
    <term name="month-12">December</term>\r
\r
    <!-- SHORT MONTH FORMS -->\r
    <!-- Chicago Manual of Style, 18th ed., sec. 10.44 (identical to New Hart's Rules, 2nd ed., sec. 10.2.6) -->\r
    <term name="month-01" form="short">Jan.</term>\r
    <term name="month-02" form="short">Feb.</term>\r
    <term name="month-03" form="short">Mar.</term>\r
    <term name="month-04" form="short">Apr.</term>\r
    <term name="month-05" form="short">May</term>\r
    <term name="month-06" form="short">June</term>\r
    <term name="month-07" form="short">July</term>\r
    <term name="month-08" form="short">Aug.</term>\r
    <term name="month-09" form="short">Sept.</term>\r
    <term name="month-10" form="short">Oct.</term>\r
    <term name="month-11" form="short">Nov.</term>\r
    <term name="month-12" form="short">Dec.</term>\r
\r
    <!-- SEASONS -->\r
    <term name="season-01">Spring</term>\r
    <term name="season-02">Summer</term>\r
    <term name="season-03">Autumn</term>\r
    <term name="season-04">Winter</term>\r
  </terms>\r
</locale>\r
`;export{r as default};
