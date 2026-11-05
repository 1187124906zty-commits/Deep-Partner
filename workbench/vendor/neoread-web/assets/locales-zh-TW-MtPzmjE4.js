const r=`<?xml version="1.0" encoding="utf-8"?>\r
<locale xmlns="http://purl.org/net/xbiblio/csl" version="1.0" xml:lang="zh-TW">\r
  <info>\r
    <translator>\r
      <name>sati-bodhi</name>\r
    </translator>\r
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>\r
    <updated>2026-01-10T00:00:00+00:00</updated>\r
  </info>\r
  <style-options punctuation-in-quote="false"/>\r
  <date form="text">\r
    <date-part name="year" suffix="年"/>\r
    <date-part name="month" form="numeric" suffix="月"/>\r
    <date-part name="day" suffix="日"/>\r
  </date>\r
  <date form="numeric">\r
    <date-part name="year"/>\r
    <date-part name="month" form="numeric-leading-zeros" prefix="/"/>\r
    <date-part name="day" form="numeric-leading-zeros" prefix="/"/>\r
  </date>\r
  <terms>\r
    <!-- LONG GENERAL TERMS -->\r
    <term name="accessed">引見於</term>\r
    <term name="advance-online-publication">advance online publication</term>\r
    <term name="album">album</term>\r
    <term name="and">及</term>\r
    <term name="and others">及其他</term>\r
    <term name="anonymous">作者不詳</term>\r
    <term name="at">於</term>\r
    <term name="audio-recording">audio recording</term>\r
    <term name="available at">載於</term>\r
    <term name="by">著</term>\r
    <term name="circa">介於</term>\r
    <term name="cited">見引於</term>\r
    <term name="et-al">等</term>\r
    <term name="film">film</term>\r
    <term name="forthcoming">即將出版</term>\r
    <term name="from">從</term>\r
    <term name="henceforth">henceforth</term>\r
    <term name="ibid">同上</term>\r
    <term name="in">收入</term>\r
    <term name="in press">印行中</term>\r
    <term name="internet">互聯網</term>\r
    <term name="letter">信函</term>\r
    <term name="loc-cit">loc. cit.</term> <!-- like ibid., the abbreviated form is the regular form  -->\r
    <term name="no date">日期不詳</term>\r
    <term name="no-place">no place</term>\r
    <term name="no-publisher">no publisher</term> <!-- sine nomine -->\r
    <term name="on">on</term>\r
    <term name="online">線上</term>\r
    <term name="op-cit">op. cit.</term> <!-- like ibid., the abbreviated form is the regular form  -->\r
    <term name="original-work-published">original work published</term>\r
    <term name="personal-communication">私人通訊</term>\r
    <term name="podcast">podcast</term>\r
    <term name="podcast-episode">podcast episode</term>\r
    <term name="preprint">preprint</term>\r
    <term name="presented at">發表於</term>\r
    <term name="radio-broadcast">radio broadcast</term>\r
    <term name="radio-series">radio series</term>\r
    <term name="radio-series-episode">radio series episode</term>\r
    <term name="reference">參考</term>\r
    <term name="retrieved">讀取於</term>\r
    <term name="review-of">review of</term>\r
    <term name="scale">比例</term>\r
    <term name="special-issue">special issue</term>\r
    <term name="special-section">special section</term>\r
    <term name="television-broadcast">television broadcast</term>\r
    <term name="television-series">television series</term>\r
    <term name="television-series-episode">television series episode</term>\r
    <term name="video">video</term>\r
    <term name="working-paper">working paper</term>\r
\r
    <!-- SHORT GENERAL TERMS -->\r
    <term name="anonymous" form="short">無名氏</term>\r
    <term name="circa" form="short">約</term>\r
    <term name="no date" form="short">不詳</term>\r
    <term name="no-place" form="short">n.p.</term>\r
    <term name="no-publisher" form="short">n.p.</term>\r
    <term name="reference" form="short">參</term>\r
    <term name="review-of" form="short">rev. of</term>\r
\r
    <!-- SYMBOLIC GENERAL FORMS -->\r
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
    <term name="classic">classic</term>\r
    <term name="collection">collection</term>\r
    <term name="dataset">dataset</term>\r
    <term name="document">document</term>\r
    <term name="entry">entry</term>\r
    <term name="entry-dictionary">dictionary entry</term>\r
    <term name="entry-encyclopedia">encyclopedia entry</term>\r
    <term name="event">event</term>\r
    <!-- figure is in the list of locator terms -->\r
    <term name="graphic">graphic</term>\r
    <term name="hearing">hearing</term>\r
    <term name="interview">訪談</term>\r
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
    <term name="personal_communication">私人通訊</term>\r
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
    <term name="article-journal" form="short">journal art.</term>\r
    <term name="article-magazine" form="short">mag. art.</term>\r
    <term name="article-newspaper" form="short">newspaper art.</term>\r
    <!-- book is in the list of locator terms -->\r
    <!-- chapter is in the list of locator terms -->\r
    <term name="document" form="short">doc.</term>\r
    <!-- figure is in the list of locator terms -->\r
    <term name="graphic" form="short">graph.</term>\r
    <term name="interview" form="short">interv.</term>\r
    <term name="manuscript" form="short">MS</term>\r
    <term name="motion_picture" form="short">video rec.</term>\r
    <term name="report" form="short">rep.</term>\r
    <term name="review" form="short">rev.</term>\r
    <term name="review-book" form="short">bk. rev.</term>\r
    <term name="song" form="short">audio rec.</term>\r
\r
    <!-- LONG VERB ITEM TYPE FORMS -->\r
    <!-- Only where applicable -->\r
    <term name="hearing" form="verb">testimony of</term>\r
    <term name="review" form="verb">review of</term>\r
    <term name="review-book" form="verb">review of the book</term>\r
\r
    <!-- SHORT VERB ITEM TYPE FORMS -->\r
\r
    <!-- HISTORICAL ERA TERMS -->\r
    <term name="ad">西元</term>\r
    <term name="bc">西元前</term>\r
    <term name="bce">BCE</term>\r
    <term name="ce">CE</term>\r
\r
    <!-- PUNCTUATION -->\r
    <term name="open-quote">「</term>\r
    <term name="close-quote">」</term>\r
    <term name="open-inner-quote">『</term>\r
    <term name="close-inner-quote">』</term>\r
    <term name="page-range-delimiter">–</term>\r
    <term name="colon">:</term>\r
    <term name="comma">,</term>\r
    <term name="semicolon">;</term>\r
\r
    <!-- ORDINALS -->\r
    <term name="ordinal"/>\r
\r
    <!-- LONG ORDINALS -->\r
    <term name="long-ordinal-01">一</term>\r
    <term name="long-ordinal-02">二</term>\r
    <term name="long-ordinal-03">三</term>\r
    <term name="long-ordinal-04">四</term>\r
    <term name="long-ordinal-05">五</term>\r
    <term name="long-ordinal-06">六</term>\r
    <term name="long-ordinal-07">七</term>\r
    <term name="long-ordinal-08">八</term>\r
    <term name="long-ordinal-09">九</term>\r
    <term name="long-ordinal-10">十</term>\r
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
    <term name="book">冊</term>\r
    <term name="canon">\r
      <single>canon</single>\r
      <multiple>canons</multiple>\r
    </term>\r
    <term name="chapter">章</term>\r
    <term name="column">欄</term>\r
    <term name="elocation">\r
      <single>location</single>\r
      <multiple>locations</multiple>\r
    </term>\r
    <term name="equation">\r
      <single>equation</single>\r
      <multiple>equations</multiple>\r
    </term>\r
    <term name="figure">圖表</term>\r
    <term name="folio">版</term>\r
    <term name="issue">期</term>\r
    <term name="line">行</term>\r
    <term name="note">註腳</term>\r
    <term name="opus">作品</term>\r
    <term name="page">頁</term>\r
    <term name="paragraph">段落</term>\r
    <term name="part">部分</term>\r
    <term name="rule">\r
      <single>rule</single>\r
      <multiple>rules</multiple>\r
    </term>\r
    <term name="scene">\r
      <single>scene</single>\r
      <multiple>scenes</multiple>\r
    </term>\r
    <term name="section">節</term>\r
    <term name="sub-verbo">另見</term>\r
    <term name="supplement">\r
      <single>supplement</single>\r
      <multiple>supplements</multiple>\r
    </term>\r
    <term name="table">\r
      <single>table</single>\r
      <multiple>tables</multiple>\r
    </term>\r
    <term name="timestamp"> <!-- generally blank -->\r
      <single/>\r
      <multiple/>\r
    </term>\r
    <term name="title-locator">\r
      <single>title</single>\r
      <multiple>titles</multiple>\r
    </term>\r
    <term name="verse">篇</term>\r
    <term name="volume">卷</term>\r
\r
    <!-- SHORT LOCATOR FORMS -->\r
    <term name="appendix" form="short">\r
      <single>app.</single>\r
      <multiple>apps.</multiple>\r
    </term>\r
    <term name="article-locator" form="short">\r
      <single>art.</single>\r
      <multiple>arts.</multiple>\r
    </term>\r
    <term name="book" form="short">冊</term>\r
    <term name="chapter" form="short">章</term>\r
    <term name="column" form="short">欄</term>\r
    <term name="elocation" form="short">\r
      <single>loc.</single>\r
      <multiple>locs.</multiple>\r
    </term>\r
    <term name="equation" form="short">\r
      <single>eq.</single>\r
      <multiple>eqs.</multiple>\r
    </term>\r
    <term name="figure" form="short">圖</term>\r
    <term name="issue" form="short">期</term>\r
    <term name="line" form="short">行</term>\r
    <term name="note" form="short">註</term>\r
    <term name="opus" form="short">op.</term>\r
    <term name="page" form="short">頁</term>\r
    <term name="paragraph" form="short">段</term>\r
    <term name="part" form="short">部</term>\r
    <term name="rule" form="short">\r
      <single>r.</single>\r
      <multiple>rr.</multiple>\r
    </term>\r
    <term name="scene" form="short">\r
      <single>sc.</single>\r
      <multiple>scs.</multiple>\r
    </term>\r
    <term name="section" form="short">節</term>\r
    <term name="sub-verbo" form="short">另見</term>\r
    <term name="supplement" form="short">\r
      <single>supp.</single>\r
      <multiple>supps.</multiple>\r
    </term>\r
    <term name="table" form="short">\r
      <single>tbl.</single>\r
      <multiple>tbls.</multiple>\r
    </term>\r
    <term name="timestamp" form="short"> <!-- generally blank -->\r
      <single/>\r
      <multiple/>\r
    </term>\r
    <term name="title-locator" form="short">\r
      <single>tit.</single>\r
      <multiple>tits.</multiple>\r
    </term>\r
    <term name="verse" form="short">篇</term>\r
    <term name="volume" form="short">卷</term>\r
\r
    <!-- SYMBOLIC LOCATOR FORMS -->\r
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
    <term name="collection-number">期</term>\r
    <term name="edition">版本</term>\r
    <term name="first-reference-note-number">註腳</term>\r
    <term name="number">\r
      <single>number</single>\r
      <multiple>numbers</multiple>\r
    </term>\r
    <term name="number-of-pages">總頁數</term>\r
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
    <term name="version">版</term>\r
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
    <term name="collection-number" form="short">期</term>\r
    <term name="edition" form="short">本</term>\r
    <term name="first-reference-note-number" form="short">註</term>\r
    <term name="number" form="short">\r
      <single>no.</single>\r
      <multiple>nos.</multiple>\r
    </term>\r
    <term name="number-of-pages" form="short">共</term>\r
    <term name="number-of-volumes" form="short">\r
      <single>vol.</single>\r
      <multiple>vols.</multiple>\r
    </term>\r
    <term name="page-first" form="short">\r
      <single>p.</single>\r
      <multiple>pp.</multiple>\r
    </term>\r
    <term name="printing" form="short">\r
      <single>print.</single>\r
      <multiple>prints.</multiple>\r
    </term>\r
\r
    <!-- LONG ROLE FORMS -->\r
    <term name="author"/> <!-- generally blank -->\r
    <term name="chair">\r
      <single>chair</single>\r
      <multiple>chairs</multiple>\r
    </term>\r
    <term name="collection-editor">\r
      <single>ed.</single>\r
      <multiple>eds.</multiple>\r
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
    <term name="director">導演</term>\r
    <term name="editor">編輯</term>\r
    <term name="editor-translator">編譯員</term>\r
    <term name="editortranslator">編譯員</term>\r
    <term name="editorial-director">主編</term>\r
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
    <term name="illustrator">繪圖師</term>\r
    <term name="interviewer"/> <!-- generally blank -->\r
    <term name="interviewer">採訪員</term>\r
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
    <term name="recipient">收信人</term>\r
    <term name="reviewed-author"/> <!-- generally blank -->\r
    <term name="reviewed-author">評論人</term>\r
    <term name="script-writer">\r
      <single>writer</single>\r
      <multiple>writers</multiple>\r
    </term>\r
    <term name="series-creator">\r
      <single>series creator</single>\r
      <multiple>series creators</multiple>\r
    </term>\r
    <term name="translator">翻譯員</term>\r
\r
    <!-- SHORT ROLE FORMS -->\r
    <term name="compiler" form="short">\r
      <single>comp.</single>\r
      <multiple>comps.</multiple>\r
    </term>\r
    <term name="contributor" form="short">\r
      <single>contrib.</single>\r
      <multiple>contribs.</multiple>\r
    </term>\r
    <term name="curator" form="short">\r
      <single>cur.</single>\r
      <multiple>curs.</multiple>\r
    </term>\r
    <term name="director" form="short">導演</term>\r
    <term name="editor" form="short">編輯</term>\r
    <term name="editor-translator" form="short">編譯員</term>\r
    <term name="editortranslator" form="short">編譯員</term>\r
    <term name="editorial-director" form="short">主編</term>\r
    <term name="executive-producer" form="short">\r
      <single>exec. prod.</single>\r
      <multiple>exec. prods.</multiple>\r
    </term>\r
    <term name="illustrator" form="short">繪圖師</term>\r
    <term name="interviewer" form="short">採訪員</term>\r
    <term name="narrator" form="short">\r
      <single>narr.</single>\r
      <multiple>narrs.</multiple>\r
    </term>\r
    <term name="organizer" form="short">\r
      <single>org.</single>\r
      <multiple>orgs.</multiple>\r
    </term>\r
    <term name="performer" form="short">\r
      <single>perf.</single>\r
      <multiple>perfs.</multiple>\r
    </term>\r
    <term name="producer" form="short">\r
      <single>prod.</single>\r
      <multiple>prods.</multiple>\r
    </term>\r
    <term name="recipient" form="short">收信人</term>\r
    <term name="reviewed-author" form="short">評論人</term>\r
    <term name="script-writer" form="short">\r
      <single>writ.</single>\r
      <multiple>writs.</multiple>\r
    </term>\r
    <term name="series-creator" form="short">\r
      <single>cre.</single>\r
      <multiple>cres.</multiple>\r
    </term>\r
    <term name="translator" form="short">翻譯員</term>\r
\r
    <!-- VERB ROLE FORMS -->\r
    <term name="chair" form="verb">chaired by</term>\r
    <term name="collection-editor" form="verb">點校</term>\r
    <term name="compiler" form="verb">compiled by</term>\r
    <term name="container-author" form="verb">著</term>\r
    <term name="contributor" form="verb">with</term>\r
    <term name="curator" form="verb">curated by</term>\r
    <term name="director" form="verb">指導</term>\r
    <term name="editor" form="verb">編輯</term>\r
    <term name="editor-translator" form="verb">編譯</term>\r
    <term name="editortranslator" form="verb">編譯</term>\r
    <term name="editorial-director" form="verb">主編</term>\r
    <term name="executive-producer" form="verb">executive produced by</term>\r
    <term name="guest" form="verb">with guest</term>\r
    <term name="host" form="verb">hosted by</term>\r
    <term name="illustrator" form="verb">繪圖</term>\r
    <term name="interviewer" form="verb">採訪</term>\r
    <term name="narrator" form="verb">narrated by</term>\r
    <term name="organizer" form="verb">organized by</term>\r
    <term name="performer" form="verb">performed by</term>\r
    <term name="producer" form="verb">produced by</term>\r
    <term name="recipient" form="verb">受函</term>\r
    <term name="reviewed-author" form="verb">點評</term>\r
    <term name="script-writer" form="verb">written by</term>\r
    <term name="series-creator" form="verb">created by</term>\r
    <term name="translator" form="verb">翻譯</term>\r
\r
    <!-- SHORT VERB ROLE FORMS -->\r
    <term name="collection-editor" form="verb-short">校</term>\r
    <term name="compiler" form="verb-short">comp. by</term>\r
    <term name="contributor" form="verb-short">w.</term>\r
    <term name="curator" form="verb-short">cur. by</term>\r
    <term name="director" form="verb-short">導</term>\r
    <term name="editor" form="verb-short">編</term>\r
    <term name="editor-translator" form="verb-short">ed. &amp; trans. by</term>\r
    <term name="editortranslator" form="verb-short">ed. &amp; trans. by</term>\r
    <term name="editorial-director" form="verb-short">編</term>\r
    <term name="executive-producer" form="verb-short">exec. prod. by</term>\r
    <term name="guest" form="verb-short">w. guest</term>\r
    <term name="host" form="verb-short">hosted by</term>\r
    <term name="illustrator" form="verb-short">繪</term>\r
    <term name="narrator" form="verb-short">narr. by</term>\r
    <term name="organizer" form="verb-short">org. by</term>\r
    <term name="performer" form="verb-short">perf. by</term>\r
    <term name="producer" form="verb-short">prod. by</term>\r
    <term name="reviewed-author" form="verb-short">評</term>\r
    <term name="script-writer" form="verb-short">writ. by</term>\r
    <term name="series-creator" form="verb-short">cre. by</term>\r
    <term name="translator" form="verb-short">譯</term>\r
\r
    <!-- LONG MONTH FORMS -->\r
    <term name="month-01">一月</term>\r
    <term name="month-02">二月</term>\r
    <term name="month-03">三月</term>\r
    <term name="month-04">四月</term>\r
    <term name="month-05">五月</term>\r
    <term name="month-06">六月</term>\r
    <term name="month-07">七月</term>\r
    <term name="month-08">八月</term>\r
    <term name="month-09">九月</term>\r
    <term name="month-10">十月</term>\r
    <term name="month-11">十一月</term>\r
    <term name="month-12">十二月</term>\r
\r
    <!-- SHORT MONTH FORMS -->\r
    <term name="month-01" form="short">1月</term>\r
    <term name="month-02" form="short">2月</term>\r
    <term name="month-03" form="short">3月</term>\r
    <term name="month-04" form="short">4月</term>\r
    <term name="month-05" form="short">5月</term>\r
    <term name="month-06" form="short">6月</term>\r
    <term name="month-07" form="short">7月</term>\r
    <term name="month-08" form="short">8月</term>\r
    <term name="month-09" form="short">9月</term>\r
    <term name="month-10" form="short">10月</term>\r
    <term name="month-11" form="short">11月</term>\r
    <term name="month-12" form="short">12月</term>\r
\r
    <!-- SEASONS -->\r
    <term name="season-01">春</term>\r
    <term name="season-02">夏</term>\r
    <term name="season-03">秋</term>\r
    <term name="season-04">冬</term>\r
  </terms>\r
</locale>\r
`;export{r as default};
