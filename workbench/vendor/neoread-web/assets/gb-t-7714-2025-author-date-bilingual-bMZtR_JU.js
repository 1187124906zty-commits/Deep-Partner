const r=`<?xml version="1.0" encoding="utf-8"?>\r
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="never" name-as-sort-order="all" sort-separator=" " initialize-with=" " page-range-format="expanded" default-locale="zh-CN">\r
  <info>\r
    <title>GB/T 7714—2025（著者-出版年，双语）</title>\r
    <id>https://zotero-chinese.com/styles/GB-T-7714—2025（著者-出版年，双语）</id>\r
    <link href="https://zotero-chinese.com/styles/GB-T-7714—2025（著者-出版年，双语）" rel="self"/>\r
    <link href="https://zotero-chinese.com/styles/GB-T-7714—2025（顺序编码，双语）" rel="template"/>\r
    <link href="https://std.samr.gov.cn/gb/search/gbDetailed?id=4507EFE13D37CB6AE06397BE0A0A601F" rel="documentation"/>\r
    <author>\r
      <name>Zeping Lee</name>\r
      <email>zepinglee@gmail.com</email>\r
    </author>\r
    <category citation-format="author-date"/>\r
    <category field="generic-base"/>\r
    <summary>GB/T 7714—2025 信息与文献 参考文献著录规则（2026-07-01实施）</summary>\r
    <updated>2026-08-09T15:54:10+08:00</updated>\r
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>\r
  </info>\r
  <locale xml:lang="en">\r
    <terms>\r
      <term name="volume" form="short">v.</term>\r
    </terms>\r
  </locale>\r
  <locale xml:lang="zh">\r
    <terms>\r
      <term name="and others"> 等</term>\r
      <term name="anonymous" form="short">佚名</term>\r
      <term name="no date" form="short">无日期</term>\r
      <term name="edition" form="short">版</term>\r
      <term name="version" form="short">v.</term>\r
      <term name="volume" form="short">第%s卷</term> <!-- CSL-M 扩展-->\r
      <term name="open-quote">“</term>\r
      <term name="close-quote">”</term>\r
      <term name="open-inner-quote">‘</term>\r
      <term name="close-inner-quote">’</term>\r
    </terms>\r
  </locale>\r
  <locale>\r
    <date form="numeric">\r
      <date-part name="year" range-delimiter="/"/>\r
      <date-part name="month" form="numeric-leading-zeros" prefix="-" range-delimiter="/"/>\r
      <date-part name="day" form="numeric-leading-zeros" prefix="-" range-delimiter="/"/>\r
    </date>\r
    <terms>\r
      <term name="and others">et al.</term>\r
      <term name="citation-range-delimiter">-</term> <!-- CSL-M 扩展-->\r
      <term name="page-range-delimiter">-</term>\r
    </terms>\r
  </locale>\r
  <!-- 主要责任者 -->\r
  <macro name="author">\r
    <names variable="composer">\r
      <name delimiter="，"/>\r
      <substitute>\r
        <names variable="author"/>\r
        <names variable="illustrator"/>\r
        <names variable="director"/>\r
        <names variable="host"/>\r
        <choose>\r
          <if variable="container-title" match="none">\r
            <names variable="editor"/>\r
            <names variable="editorial-director"/>\r
            <names variable="compiler"/>\r
            <names variable="collection-editor"/>\r
          </if>\r
        </choose>\r
        <text macro="anon"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <macro name="author-intext-en">\r
    <names variable="composer">\r
      <name form="short" delimiter="，" and="text"/>\r
      <substitute>\r
        <names variable="author"/>\r
        <names variable="illustrator"/>\r
        <names variable="director"/>\r
        <names variable="host"/>\r
        <choose>\r
          <if variable="container-title" match="none">\r
            <names variable="editor"/>\r
            <names variable="editorial-director"/>\r
            <names variable="compiler"/>\r
            <names variable="collection-editor"/>\r
          </if>\r
        </choose>\r
        <text macro="anon"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <macro name="author-intext-zh">\r
    <names variable="composer">\r
      <name delimiter="，" and="text"/>\r
      <et-al term="and others"/>\r
      <substitute>\r
        <names variable="author"/>\r
        <names variable="illustrator"/>\r
        <names variable="director"/>\r
        <names variable="host"/>\r
        <choose>\r
          <if variable="container-title" match="none">\r
            <names variable="editor"/>\r
            <names variable="editorial-director"/>\r
            <names variable="compiler"/>\r
            <names variable="collection-editor"/>\r
          </if>\r
        </choose>\r
        <text macro="anon"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <macro name="anon">\r
    <text term="anonymous" form="short" strip-periods="true" text-case="capitalize-first"/>\r
  </macro>\r
  <macro name="date-intext">\r
    <choose>\r
      <if type="article-journal article-magazine" match="any">\r
        <choose>\r
          <if variable="volume issue" match="any">\r
            <date variable="issued">\r
              <date-part name="year" range-delimiter="-"/>\r
            </date>\r
            <text variable="year-suffix"/>\r
          </if>\r
          <else-if variable="available-date">\r
            <date variable="available-date">\r
              <date-part name="year" range-delimiter="-"/>\r
            </date>\r
            <text variable="year-suffix"/>\r
          </else-if>\r
          <else>\r
            <date variable="issued">\r
              <date-part name="year" range-delimiter="-"/>\r
            </date>\r
            <text variable="year-suffix"/>\r
          </else>\r
        </choose>\r
      </if>\r
      <else-if variable="issued">\r
        <date variable="issued">\r
          <date-part name="year" range-delimiter="-"/>\r
        </date>\r
        <text variable="year-suffix"/>\r
      </else-if>\r
      <else-if variable="accessed">\r
        <group prefix="[" suffix="]">\r
          <date variable="accessed">\r
            <date-part name="year" range-delimiter="-"/>\r
          </date>\r
          <text variable="year-suffix"/>\r
        </group>\r
      </else-if>\r
      <else>\r
        <group delimiter="-">\r
          <text term="no date" form="short"/>\r
          <text variable="year-suffix"/>\r
        </group>\r
      </else>\r
    </choose>\r
  </macro>\r
  <!-- 题名 -->\r
  <macro name="title">\r
    <group delimiter=". ">\r
      <group delimiter="：">\r
        <text variable="title"/>\r
        <choose>\r
          <if variable="container-title" type="chapter entry-dictionary entry-encyclopedia paper-conference" match="none">\r
            <group delimiter="&#8195;">\r
              <text macro="volume"/>\r
              <text variable="volume-title"/>\r
            </group>\r
          </if>\r
        </choose>\r
        <choose>\r
          <if type="article article-journal standard" match="none">\r
            <!-- 预印本、期刊文章、标准的编号在其他位置 -->\r
            <text macro="number"/>\r
          </if>\r
        </choose>\r
      </group>\r
      <choose>\r
        <if type="map">\r
          <text variable="scale"/>\r
        </if>\r
      </choose>\r
    </group>\r
    <group delimiter="/" prefix="[" suffix="]">\r
      <text macro="entry-type-id"/>\r
      <text macro="entry-medium-id"/>\r
    </group>\r
  </macro>\r
  <!-- 多卷书的卷次 -->\r
  <macro name="volume">\r
    <choose>\r
      <if type="article article-journal article-magazine article-newspaper periodical" match="none">\r
        <choose>\r
          <if is-numeric="volume">\r
            <label variable="volume" form="short"/>\r
            <text variable="volume"/>\r
          </if>\r
          <else>\r
            <text variable="volume"/>\r
          </else>\r
        </choose>\r
      </if>\r
    </choose>\r
  </macro>\r
  <!-- 报告编号、标准号、专利申请号、档号 -->\r
  <macro name="number">\r
    <choose>\r
      <if type="patent" variable="call-number" match="all">\r
        <!-- 专利优先使用申请号 -->\r
        <text variable="call-number"/>\r
      </if>\r
      <else-if variable="number">\r
        <text variable="number"/>\r
      </else-if>\r
      <else-if type="collection manuscript personal_communication" variable="archive" match="any">\r
        <!-- 档案的档号 -->\r
        <text variable="archive_location"/>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <!-- 文献类型标识 -->\r
  <macro name="entry-type-id">\r
    <choose>\r
      <if type="article">\r
        <!-- 预印本 -->\r
        <text value="PP"/>\r
      </if>\r
      <else-if type="article-journal article-magazine periodical" match="any">\r
        <text value="J"/>\r
      </else-if>\r
      <else-if type="article-newspaper">\r
        <text value="N"/>\r
      </else-if>\r
      <else-if type="bill collection hearing legal_case legislation personal_communication regulation treaty" match="any">\r
        <text value="A"/>\r
      </else-if>\r
      <else-if type="book chapter classic entry-dictionary entry-encyclopedia" match="any">\r
        <text value="M"/>\r
      </else-if>\r
      <else-if type="dataset">\r
        <text value="DS"/>\r
      </else-if>\r
      <else-if type="map">\r
        <text value="CM"/>\r
      </else-if>\r
      <else-if type="paper-conference">\r
        <text value="C"/>\r
      </else-if>\r
      <else-if type="patent">\r
        <text value="P"/>\r
      </else-if>\r
      <else-if type="post post-weblog webpage" match="any">\r
        <text value="EB"/>\r
      </else-if>\r
      <else-if type="report">\r
        <text value="R"/>\r
      </else-if>\r
      <else-if type="software">\r
        <text value="CP"/>\r
      </else-if>\r
      <else-if type="standard">\r
        <text value="S"/>\r
      </else-if>\r
      <else-if type="thesis">\r
        <text value="D"/>\r
      </else-if>\r
      <else-if variable="archive">\r
        <text value="A"/>\r
      </else-if>\r
      <else-if variable="CSTR DOI URL" match="any">\r
        <text value="EB"/>\r
      </else-if>\r
      <else>\r
        <text value="Z"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <!-- 文献载体标识 -->\r
  <macro name="entry-medium-id">\r
    <choose>\r
      <if variable="medium">\r
        <text variable="medium"/>\r
      </if>\r
      <else-if variable="URL DOI" match="any">\r
        <text value="OL"/>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <!-- 其他责任者 -->\r
  <macro name="secondary-contributors">\r
    <names variable="translator">\r
      <name delimiter="，"/>\r
      <label form="short" prefix="，"/>\r
    </names>\r
  </macro>\r
  <!-- 图书主要责任者 -->\r
  <macro name="container-contributors">\r
    <names variable="container-author">\r
      <name delimiter="，"/>\r
      <substitute>\r
        <names variable="editor"/>\r
        <names variable="editorial-director"/>\r
        <names variable="compiler"/>\r
        <names variable="collection-editor"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <!-- 图书题名 -->\r
  <macro name="container-booklike">\r
    <choose>\r
      <if variable="container-title">\r
        <group delimiter=". ">\r
          <text macro="container-contributors"/>\r
          <group delimiter="：">\r
            <text variable="container-title"/>\r
            <text macro="volume"/>\r
          </group>\r
        </group>\r
      </if>\r
    </choose>\r
  </macro>\r
  <!-- 连续出版物中的出处项 -->\r
  <macro name="container-periodical">\r
    <choose>\r
      <if type="article-newspaper">\r
        <!-- 报纸的出处项：“刊名，出版日期（版次）：页码” -->\r
        <group delimiter="，">\r
          <text variable="container-title" strip-periods="true"/>\r
          <text macro="date"/>\r
        </group>\r
        <text variable="page" prefix="（" suffix="）"/>\r
      </if>\r
      <else>\r
        <!-- 期刊、杂志的出处项：“刊名，卷（期）：页码” -->\r
        <group delimiter="：">\r
          <group>\r
            <group delimiter="，">\r
              <text variable="container-title" strip-periods="true"/>\r
              <choose>\r
                <if variable="volume issue" match="none">\r
                  <!-- 无卷号和期号，视为在线出版文章，优先使用在线出版日期 -->\r
                  <choose>\r
                    <if variable="available-date">\r
                      <date variable="available-date" form="numeric"/>\r
                    </if>\r
                    <else>\r
                      <date variable="issued" form="numeric"/>\r
                    </else>\r
                  </choose>\r
                </if>\r
              </choose>\r
              <text variable="volume"/>\r
            </group>\r
            <text variable="issue" prefix="（" suffix="）"/>\r
          </group>\r
          <choose>\r
            <if variable="page">\r
              <text variable="page"/>\r
            </if>\r
            <else>\r
              <!-- 无页码有文章编号的，应将文章编号按页码著录 -->\r
              <text variable="number"/>\r
            </else>\r
          </choose>\r
        </group>\r
      </else>\r
    </choose>\r
  </macro>\r
  <!-- 版本项 -->\r
  <macro name="edition">\r
    <choose>\r
      <if is-numeric="edition">\r
        <group delimiter=" ">\r
          <number variable="edition" form="ordinal"/>\r
          <label variable="edition" form="short"/>\r
        </group>\r
      </if>\r
      <else>\r
        <text variable="edition"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <macro name="version">\r
    <label variable="version" form="short" text-case="capitalize-first" strip-periods="true"/>\r
    <text variable="version"/>\r
  </macro>\r
  <!-- 7.5 出版信息 7.7 页码 -->\r
  <macro name="publisher">\r
    <choose>\r
      <if type="article dataset" match="any">\r
        <text variable="publisher"/>\r
      </if>\r
      <else-if type="book chapter classic entry-dictionary entry-encyclopedia map paper-conference periodical thesis" variable="publisher" match="any">\r
        <group delimiter="：">\r
          <group delimiter="：">\r
            <text variable="publisher-place"/>\r
            <text variable="publisher"/>\r
          </group>\r
          <text variable="page"/>\r
        </group>\r
      </else-if>\r
      <else-if type="patent report" match="any">\r
        <group delimiter="：">\r
          <text macro="date"/>\r
          <text variable="page"/>\r
        </group>\r
      </else-if>\r
      <else-if type="collection manuscript personal_communication" variable="archive" match="any">\r
        <!-- 档案中的收藏者所在地、收藏者、形成日期 -->\r
        <group delimiter="，">\r
          <group delimiter="：">\r
            <text variable="archive-place"/>\r
            <text variable="archive"/>\r
          </group>\r
          <text macro="date"/>\r
        </group>\r
      </else-if>\r
      <else-if type="post post-weblog webpage" variable="CSTR DOI URL" match="none">\r
        <group delimiter="：">\r
          <group delimiter="：">\r
            <text variable="publisher-place"/>\r
            <text variable="publisher"/>\r
          </group>\r
          <text variable="page"/>\r
        </group>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <!-- 出版日期 -->\r
  <macro name="date">\r
    <choose>\r
      <if variable="issued">\r
        <choose>\r
          <if type="report" variable="publisher" match="all">\r
            <!-- 以图书、图书中的析出文献形式出现的报告 -->\r
          </if>\r
          <else-if type="article-newspaper collection patent manuscript personal_communication report" variable="archive" match="any">\r
            <date variable="issued" form="numeric"/>\r
          </else-if>\r
        </choose>\r
      </if>\r
    </choose>\r
  </macro>\r
  <!-- 地图的尺寸 -->\r
  <macro name="dimensions">\r
    <choose>\r
      <if type="map">\r
        <text variable="dimensions"/>\r
      </if>\r
    </choose>\r
  </macro>\r
  <!-- 7.6 创建/发布日期或修改日期、引用日期 -->\r
  <macro name="creation-accessed-date">\r
    <date variable="issued" form="numeric" prefix="（" suffix="）"/>\r
    <date variable="accessed" form="numeric" prefix="[" suffix="]"/>\r
  </macro>\r
  <!-- 7.8 获取和访问路径 7.9 永久标识符 -->\r
  <macro name="access">\r
    <group delimiter=". ">\r
      <text variable="URL"/>\r
      <choose>\r
        <if variable="CSTR"> <!-- 扩展：CSTR -->\r
          <text variable="CSTR" prefix="CSTR:"/>\r
        </if>\r
        <else>\r
          <text variable="DOI" prefix="DOI:"/>\r
        </else>\r
      </choose>\r
    </group>\r
  </macro>\r
  <!-- 参考文献表格式 -->\r
  <macro name="entry-layout">\r
    <group delimiter=". ">\r
      <group delimiter="，">\r
        <text macro="author"/>\r
        <text macro="date-intext"/>\r
      </group>\r
      <choose>\r
        <if type="article-journal article-magazine article-newspaper" match="any">\r
          <!-- 8.5 连续出版物中的析出文献 -->\r
          <text macro="title"/>\r
          <text macro="secondary-contributors"/>\r
          <text macro="container-periodical"/>\r
        </if>\r
        <else-if type="post post-weblog webpage" match="any">\r
          <!-- 8.11 网站和网页 -->\r
          <text macro="title"/>\r
          <text macro="creation-accessed-date"/>\r
        </else-if>\r
        <else-if type="chapter entry-dictionary entry-encyclopedia" variable="container-title" match="any">\r
          <!-- 8.3 图书中的析出文献或 -->\r
          <group delimiter="//">\r
            <group delimiter=". ">\r
              <text macro="title"/>\r
              <text macro="secondary-contributors"/>\r
            </group>\r
            <text macro="container-booklike"/>\r
          </group>\r
          <text macro="edition"/>\r
          <text macro="publisher"/>\r
        </else-if>\r
        <else-if type="periodical">\r
          <!-- 8.4 连续出版物 -->\r
          <text macro="title"/>\r
          <text variable="volume"/> <!-- 年卷期或其他标识，如“1957（1）—1990（4）” -->\r
          <text macro="publisher"/>\r
        </else-if>\r
        <else-if type="paper-conference">\r
          <!-- 8.6 会议录 -->\r
          <group delimiter="//">\r
            <group delimiter=". ">\r
              <text macro="title"/>\r
            </group>\r
            <group delimiter="：">\r
              <text variable="event-title"/>\r
              <text variable="page"/>\r
            </group>\r
          </group>\r
        </else-if>\r
        <else-if type="standard">\r
          <!-- 8.9 标准 -->\r
          <group delimiter="&#8195;">\r
            <text variable="number"/>\r
            <text macro="title"/>\r
          </group>\r
        </else-if>\r
        <else-if type="article dataset" match="any">\r
          <!-- 8.14 数据集、8.15 预印本 -->\r
          <text macro="title"/>\r
          <text macro="version"/>\r
          <group>\r
            <text macro="publisher"/>\r
            <text macro="creation-accessed-date"/>\r
          </group>\r
        </else-if>\r
        <else-if type="book classic map patent report" variable="publisher" match="any">\r
          <!-- 8.2 图书 -->\r
          <text macro="title"/>\r
          <text macro="secondary-contributors"/>\r
          <text macro="edition"/>\r
          <text macro="publisher"/>\r
          <text macro="dimensions"/>\r
        </else-if>\r
        <else-if type="collection manuscript personal_communication" variable="archive" match="any">\r
          <!-- 8.12 档案 -->\r
          <text macro="title"/>\r
          <text macro="publisher"/>\r
        </else-if>\r
        <else-if variable="CSTR DOI URL" match="any">\r
          <!-- 其他电子资源 -->\r
          <text macro="title"/>\r
          <text macro="version"/>\r
          <text macro="creation-accessed-date"/>\r
        </else-if>\r
        <else>\r
          <text macro="title"/>\r
          <text macro="secondary-contributors"/>\r
          <text macro="edition"/>\r
          <text macro="publisher"/>\r
        </else>\r
      </choose>\r
      <text macro="access"/>\r
    </group>\r
  </macro>\r
  <citation et-al-min="2" et-al-use-first="1" disambiguate-add-givenname="true" disambiguate-add-year-suffix="true" collapse="year">\r
    <sort>\r
      <key macro="author-intext-en"/>\r
      <key macro="date-intext"/>\r
    </sort>\r
    <layout prefix="（" suffix="）" delimiter="；" locale="en"> <!-- CSL-M 扩展 -->\r
      <group delimiter="，">\r
        <text macro="author-intext-en"/>\r
        <text macro="date-intext"/>\r
      </group>\r
    </layout>\r
    <layout prefix="（" suffix="）" delimiter="；">\r
      <group delimiter="，">\r
        <text macro="author-intext-zh"/>\r
        <text macro="date-intext"/>\r
      </group>\r
    </layout>\r
  </citation>\r
  <bibliography entry-spacing="0" et-al-min="4" et-al-use-first="3" hanging-indent="true">\r
    <sort>\r
      <key macro="author"/>\r
      <key macro="date-intext"/>\r
    </sort>\r
    <layout locale="en"> <!-- CSL-M 扩展 -->\r
      <text macro="entry-layout" suffix="."/>\r
    </layout>\r
    <layout>\r
      <text macro="entry-layout" suffix="."/>\r
    </layout>\r
  </bibliography>\r
</style>\r
`;export{r as default};
