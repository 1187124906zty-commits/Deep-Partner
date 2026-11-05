const r=`<?xml version="1.0" encoding="utf-8"?>\r
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" name-as-sort-order="all" sort-separator=" " demote-non-dropping-particle="never" initialize-with=" " initialize-with-hyphen="false" page-range-format="expanded" default-locale="zh-CN">\r
  <info>\r
    <title>GB/T 7714—2015（著者-出版年，双语）</title>\r
    <id>https://zotero-chinese.com/styles/GB-T-7714—2015（著者-出版年，双语）</id>\r
    <link href="https://zotero-chinese.com/styles/GB-T-7714—2015（著者-出版年，双语）" rel="self"/>\r
    <link href="http://www.zotero.org/styles/china-national-standard-gb-t-7714-2015-author-date" rel="template"/>\r
    <link href="https://std.samr.gov.cn/gb/search/gbDetailed?id=71F772D8055ED3A7E05397BE0A0AB82A" rel="documentation"/>\r
    <author>\r
      <name>牛耕田</name>\r
      <email>buffalo_d@163.com</email>\r
    </author>\r
    <contributor>\r
      <name>Zeping Lee</name>\r
      <email>zepinglee@gmail.com</email>\r
    </contributor>\r
    <category citation-format="author-date"/>\r
    <category field="generic-base"/>\r
    <summary>按照语言显示“等”或“et al.”</summary>\r
    <updated>2026-08-09T17:10:28+08:00</updated>\r
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>\r
  </info>\r
  <locale xml:lang="zh">\r
    <terms>\r
      <term name="anonymous" form="short">佚名</term>\r
      <term name="edition" form="short">版</term>\r
      <term name="and others"> 等</term>\r
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
      <term name="page-range-delimiter">-</term>\r
    </terms>\r
  </locale>\r
  <!-- 主要责任者 -->\r
  <macro name="author">\r
    <names variable="author">\r
      <name delimiter="，">\r
        <name-part name="family" text-case="uppercase"/>\r
      </name>\r
      <institution/>\r
      <substitute>\r
        <names variable="composer"/>\r
        <names variable="illustrator"/>\r
        <names variable="director"/>\r
        <choose>\r
          <if variable="container-title" match="none">\r
            <names variable="editor"/>\r
          </if>\r
        </choose>\r
        <text macro="anon"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <!-- 正文中引用，对欧美著者只标注第一个著者的姓 -->\r
  <macro name="author-intext-en">\r
    <names variable="author">\r
      <name form="short" and="text"/>\r
      <substitute>\r
        <names variable="composer"/>\r
        <names variable="illustrator"/>\r
        <names variable="director"/>\r
        <choose>\r
          <if variable="container-title" match="none">\r
            <names variable="editor"/>\r
          </if>\r
        </choose>\r
        <text macro="anon"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <!-- 正文中的引用，对中国著者标注第一著者的姓名 -->\r
  <macro name="author-intext-zh">\r
    <names variable="author">\r
      <name and="text"/>\r
      <!-- 国标 10.2.2 节要求姓氏与“et al.”“等”之间留适当空隙 -->\r
      <et-al term="and others"/>\r
      <substitute>\r
        <names variable="composer"/>\r
        <names variable="illustrator"/>\r
        <names variable="director"/>\r
        <choose>\r
          <if variable="container-title" match="none">\r
            <names variable="editor"/>\r
          </if>\r
        </choose>\r
        <text macro="anon"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <macro name="anon">\r
    <text term="anonymous" form="short" strip-periods="true" text-case="capitalize-first"/>\r
  </macro>\r
  <!-- 题名 -->\r
  <macro name="title">\r
    <group delimiter="：">\r
      <text variable="title"/>\r
      <group delimiter="&#8195;">\r
        <choose>\r
          <if variable="container-title" type="chapter entry-dictionary entry-encyclopedia paper-conference" match="none">\r
            <text macro="volume"/>\r
            <text variable="volume-title"/>\r
          </if>\r
        </choose>\r
        <choose>\r
          <if type="article article-journal" match="none">\r
            <!-- 预印本和期刊文章的编号用于其他位置 -->\r
            <text variable="number"/>\r
          </if>\r
        </choose>\r
        <choose>\r
          <if type="collection manuscript personal_communication" match="any">\r
            <!-- 档案的卷宗号 -->\r
            <text variable="archive_location"/>\r
          </if>\r
        </choose>\r
      </group>\r
    </group>\r
    <group delimiter="/" prefix="[" suffix="]">\r
      <text macro="entry-type-id"/>\r
      <text macro="entry-medium-id"/>\r
    </group>\r
  </macro>\r
  <!-- 书籍的卷号（“第 x 卷”或“第 x 册”） -->\r
  <macro name="volume">\r
    <choose>\r
      <if type="article article-journal article-magazine article-newspaper periodical" match="none">\r
        <choose>\r
          <if is-numeric="volume">\r
            <group delimiter=" ">\r
              <label variable="volume" form="short" text-case="capitalize-first"/>\r
              <text variable="volume"/>\r
            </group>\r
          </if>\r
          <else>\r
            <text variable="volume"/>\r
          </else>\r
        </choose>\r
      </if>\r
    </choose>\r
  </macro>\r
  <!-- 文献类型标识 -->\r
  <macro name="entry-type-id">\r
    <choose>\r
      <if type="article">\r
        <!-- 预印本使用“EB”（2005 和 2015 版国标） -->\r
        <text value="EB"/>\r
      </if>\r
      <else-if type="article-journal article-magazine periodical" match="any">\r
        <text value="J"/>\r
      </else-if>\r
      <else-if type="article-newspaper">\r
        <text value="N"/>\r
      </else-if>\r
      <else-if type="bill collection hearing legal_case legislation personal_communication regulation treaty" match="any">\r
        <!-- 档案，A：分类保存以备查考的文件和材料，如人事档案、科技档案、法律法规、政府文件等。 -->\r
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
      <else-if variable="DOI URL" match="any">\r
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
      <name delimiter="，">\r
        <name-part name="family" text-case="uppercase"/>\r
      </name>\r
      <institution/>\r
      <label form="short" prefix="，"/>\r
    </names>\r
  </macro>\r
  <!-- 专著主要责任者 -->\r
  <macro name="container-contributors">\r
    <names variable="editor">\r
      <name delimiter="，">\r
        <name-part name="family" text-case="uppercase"/>\r
      </name>\r
      <institution/>\r
      <substitute>\r
        <names variable="editorial-director"/>\r
        <names variable="collection-editor"/>\r
        <names variable="container-author"/>\r
      </substitute>\r
    </names>\r
  </macro>\r
  <!-- 专著题名 -->\r
  <macro name="container-booklike">\r
    <group delimiter=". ">\r
      <text macro="container-contributors"/>\r
      <choose>\r
        <if variable="container-title">\r
          <!-- 优先使用专著或会议论文集的题名 -->\r
          <group delimiter="：">\r
            <text variable="container-title"/>\r
            <text macro="volume"/>\r
          </group>\r
        </if>\r
        <else-if type="paper-conference">\r
          <!-- 有些会议没有论文集，使用会议名代替 -->\r
          <text variable="event-title"/>\r
        </else-if>\r
      </choose>\r
    </group>\r
  </macro>\r
  <!-- 连续出版物中的出处项 -->\r
  <macro name="container-periodical">\r
    <choose>\r
      <if type="article-newspaper">\r
        <!-- 报纸的出处项：“刊名，出版日期（版次）：页码[引用日期]” -->\r
        <group delimiter="，">\r
          <text variable="container-title"/>\r
          <text macro="issued-date"/>\r
        </group>\r
        <text variable="page" prefix="（" suffix="）"/>\r
      </if>\r
      <else>\r
        <!-- 期刊、杂志的出处项：“刊名，卷(期)：页码[引用日期]” -->\r
        <group delimiter="：">\r
          <group>\r
            <group delimiter="，">\r
              <text variable="container-title"/>\r
              <text variable="volume"/>\r
            </group>\r
            <text variable="issue" prefix="（" suffix="）"/>\r
          </group>\r
          <choose>\r
            <if variable="page">\r
              <text variable="page"/>\r
            </if>\r
            <else>\r
              <text variable="number"/>\r
            </else>\r
          </choose>\r
        </group>\r
      </else>\r
    </choose>\r
    <text macro="accessed-date"/>\r
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
  <!-- 连续出版物的年卷期 -->\r
  <macro name="year-volume-issue">\r
    <group delimiter="，">\r
      <text macro="issued-year"/>\r
      <text variable="volume"/>\r
    </group>\r
    <text variable="issue" prefix="（" suffix="）"/>\r
  </macro>\r
  <!-- 出版项 -->\r
  <macro name="publisher">\r
    <choose>\r
      <if type="patent">\r
        <!-- 专利的出版项格式“公告日期[引用日期]” -->\r
        <text macro="issued-date"/>\r
        <text macro="accessed-date"/>\r
      </if>\r
      <else-if type="book chapter paper-conference periodical thesis" variable="archive archive-place publisher publisher-place page" match="any">\r
        <!-- 非纯电子资源的格式“出版地：出版者，出版年：页码[引用日期]” -->\r
        <group delimiter="：">\r
          <group delimiter="：">\r
            <choose>\r
              <if variable="publisher publisher-place" match="any">\r
                <text variable="publisher-place"/>\r
                <text variable="publisher"/>\r
              </if>\r
              <else>\r
                <!-- 档案的馆藏地以及收藏机构或单位 -->\r
                <text variable="archive-place"/>\r
                <text variable="archive"/>\r
              </else>\r
            </choose>\r
          </group>\r
          <text variable="page"/>\r
        </group>\r
        <text macro="accessed-date"/>\r
      </else-if>\r
      <else-if variable="URL DOI" match="any">\r
        <!-- 纯电子资源联机网络文献的格式“（更新或修改日期）[引用日期]”。\r
          原国标中，电子公告、无出版社的报告、法规等文献都可以作为“纯电子文献”。\r
        -->\r
        <choose>\r
          <if has-day="issued">\r
            <text macro="issued-date" prefix="（" suffix="）"/>\r
          </if>\r
        </choose>\r
        <text macro="accessed-date"/>\r
      </else-if>\r
    </choose>\r
  </macro>\r
  <!-- 出版年 -->\r
  <macro name="issued-year">\r
    <choose>\r
      <if variable="issued">\r
        <choose>\r
          <if is-uncertain-date="issued">\r
            <!-- 出版年无法确定时, 估计的出版年应置于方括号内。 -->\r
            <date variable="issued" form="numeric" date-parts="year" prefix="[" suffix="]"/>\r
          </if>\r
          <else>\r
            <date variable="issued" form="numeric" date-parts="year"/>\r
          </else>\r
        </choose>\r
      </if>\r
      <else>\r
        <!-- 选取引用日期的年份作为估计的出版年 -->\r
        <date variable="accessed" form="numeric" date-parts="year" prefix="[" suffix="]"/>\r
      </else>\r
    </choose>\r
  </macro>\r
  <!-- 出版日期，用于报纸文献、专利的“公告日期或公开日期”、电子资源的“更新或修改日期” -->\r
  <macro name="issued-date">\r
    <date variable="issued" form="numeric"/>\r
  </macro>\r
  <!-- 引用日期 -->\r
  <macro name="accessed-date">\r
    <choose>\r
      <if variable="URL DOI" match="any">\r
        <date variable="accessed" form="numeric" prefix="[" suffix="]"/>\r
      </if>\r
    </choose>\r
  </macro>\r
  <!-- 获取和访问路径、数字对象唯一标识符 -->\r
  <macro name="access">\r
    <group delimiter=". ">\r
      <text variable="URL"/>\r
      <text variable="DOI" prefix="DOI:"/>\r
    </group>\r
  </macro>\r
  <!-- 参考文献表格式 -->\r
  <macro name="entry-layout">\r
    <group delimiter=". ">\r
      <group delimiter="，">\r
        <text macro="author"/>\r
        <text macro="issued-year"/>\r
      </group>\r
      <choose>\r
        <if type="periodical">\r
          <!-- 4.3 连续出版物 -->\r
          <text macro="title"/>\r
          <text macro="year-volume-issue"/>\r
          <text macro="publisher"/>\r
        </if>\r
        <else-if type="article-journal article-magazine article-newspaper" match="any">\r
          <!-- 4.4 连续出版物中的析出文献 -->\r
          <text macro="title"/>\r
          <text macro="container-periodical"/>\r
        </else-if>\r
        <else-if type="patent">\r
          <!-- 4.5 专利文献 -->\r
          <text macro="title"/>\r
          <text macro="publisher"/>\r
        </else-if>\r
        <else-if type="dataset post post-weblog software webpage" match="any">\r
          <!-- 4.6 电子资源 -->\r
          <text macro="title"/>\r
          <text macro="publisher"/>\r
        </else-if>\r
        <else-if type="chapter entry-dictionary entry-encyclopedia paper-conference" variable="container-title" match="any">\r
          <!-- 4.2 专著中的析出文献 -->\r
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
        <else>\r
          <!-- 4.1 专著 -->\r
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
      <key macro="issued-year"/>\r
    </sort>\r
    <layout prefix="（" suffix="）" delimiter="；" locale="en">\r
      <group delimiter="，">\r
        <text macro="author-intext-en"/>\r
        <text macro="issued-year"/>\r
      </group>\r
    </layout>\r
    <layout prefix="（" suffix="）" delimiter="；">\r
      <group delimiter="，">\r
        <text macro="author-intext-zh"/>\r
        <text macro="issued-year"/>\r
      </group>\r
    </layout>\r
  </citation>\r
  <bibliography entry-spacing="0" et-al-min="4" et-al-use-first="3" hanging-indent="true">\r
    <sort>\r
      <key macro="author"/>\r
      <key macro="issued-year"/>\r
    </sort>\r
    <layout locale="en">\r
      <text macro="entry-layout" suffix="."/>\r
    </layout>\r
    <layout>\r
      <text macro="entry-layout" suffix="."/>\r
    </layout>\r
  </bibliography>\r
</style>\r
`;export{r as default};
