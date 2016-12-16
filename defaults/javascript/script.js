// Only once the DOM is ready.
$(document).ready(function(){
	
	$("html").css("overflow", "auto");
	document.body.style.overflow = "auto";
	
	//// Get all the entries on the page.
	
	var articles = document.querySelectorAll("article");
	articles = Array.prototype.slice.call(articles, 0, articles.length);
	
	// Images start off hidden, show them once they've loaded.
	articles.forEach(function(element, index, array){

		// Only show images if they are loaded or when they have finished loading.
		$(element).children(".imagebody").children("img").each(function(){
			
			$(this).on("load", function(){
				
				$(this).animate(
					{
						opacity: 1
					}, 
					400 
				);
				
			});
			
			// Loading from cache, or it loaded before we set the load callback. So trigger it manually.
			if(this.complete){
				$(this).trigger("load");
			}
		});
		
		// Hide videos until they have loaded.
		var controls = $(element).children(".videobody").children(".controls")[0];
		$(controls).css("opacity", 0);
		
		$(element).children(".videobody").children("video").each(function(){
			$(this).css("opacity", 0);
			
			// Show the video when we have some data.
			$(this).on("loadedmetadata", function(){
				$(this).animate(
					{
						opacity: 1
					}, 
					400 
				);
				
				$(controls).animate(
					{
						opacity: 1
					}, 
					400 
				);
			});
		});
	});
	
	// Grab the videos and links.
	var bodies = document.querySelectorAll(".videobody");
	bodies = Array.prototype.slice.call(bodies, 0, bodies.length);
	
	var links = document.querySelectorAll("a.more");
	links = Array.prototype.slice.call(links, 0, links.length);
	
	// Helper functions.
	function disableScrolling(){
		$("html").css("overflow", "hidden");
		document.body.style.overflow = "hidden";
		
		$("html").css("position", "relative");
		document.body.style.position = "relative";
	}
	
	function enableScrolling(){
		$("html").css("overflow", "auto");
		document.body.style.overflow = "auto";
	}
	
	//// Handle detail clicks/modal page loading.
	
	links.forEach(function(element, index, array){
	
		element.addEventListener("click", function(e){
			
			e.preventDefault ? e.preventDefault() : e.returnValue = false;
			
			var frame = document.createElement("div"),
				loc = $(element).attr("href"),
				parts = loc.split("/"),
				directory = parts.splice(0, parts.length - 1).join("/") + "/",
				insert = "";	
	
			frame.className = "frame";			
			frame.style.top = "0";
			
			disableScrolling();
			
			frame.className += " active";
			
			// Close the frame by clicking on it.
			$(frame).bind('click', function(event) { 
				$(frame).remove();
				enableScrolling();
			});
			
			$("body").append(frame);
			
			function showFrame(){
				
				var container = frame.querySelector(".frame .container"),
					img = frame.querySelector(".frame .container p:first-child a img"),				
					link = frame.querySelectorAll(".frame .container p a"),
					allImgs = frame.querySelectorAll(".frame .container img"),
					allLinks = frame.querySelectorAll(".frame .container a"),
					close = frame.querySelector(".close");
					
					currentLink = "",
					currentImg = "";
				
				// Stop clicks on the content from closing the frame.
				$(frame.querySelector("div.container")).click(function(event){
				    event.stopPropagation();    
				});
				
				// Close the frame if we click on close or outside the content.
				$(frame.querySelector(".close")).click(function(event){
					
					event.preventDefault();
					event.stopPropagation();
					
				    $(frame).remove();
					enableScrolling();
				});
				
				$(frame).bind('click', function(event) { 
					$(frame).remove();
					enableScrolling();
				});
				
				
				/*
				// Update the images with the correct paths. These get messed up in the markdown rendering process.
				// This whole thing only really works if JS is enabled.
				currentLink = $(link).attr("href");
				$(link).attr("href", directory + currentLink);
				
				// Update the image URL to the correct location.
				// If JS is disabled, the html page loads as normal and the images still work.
				currentImg = $(img).attr("src");
				$(img).attr("src", directory + currentImg);
				*/
				
				
				
				
				$(allLinks).each(function(){
					if($(this).has("img").length){
						currentLink = $(this).attr("href");
						$(this).attr("href", directory + currentLink);
					}
					
					re = /^images\/.*/;
					if(re.test($(this).attr("href"))){
						currentLink = $(this).attr("href");
						$(this).attr("href", directory + currentLink);
					}
				});
				
				$(allImgs).each(function(){
					currentImg = $(this).attr("src");
					$(this).attr("src", directory + currentImg);
				});
				
				// Only show the frame once the main image has loaded.
				if(img){
					$(img).on("load", function(){
						container.className += " active";
					});
				}
				else{
					container.className += " active";
				}
				
				
			}
			
			// Grab the entry from the .html file and insert it into the page.
			$.ajax({
	            url : loc,
	            dataType: "text",
	            success : function (data) {
	                
	                insert = data.split("\n").slice(1).join("\n");
	                
	                frame.innerHTML = insert;
					showFrame();
	            }
        	});
		});
	});
	
	//// Handle video controls.
	
	function toggleVideo(videobody){
		
		var video = videobody.children[1],
			playButton = videobody.children[0];
		
		if(!video.paused){ // If we are playing...
			
			$(videobody).removeClass("playing");
			$(playButton.children[0]).removeClass("fa-pause");
			$(playButton.children[0]).addClass("fa-play");
			
			video.pause();
		}
		else{ // We're not playing...
			
			$(videobody).addClass("playing");
			$(playButton.children[0]).removeClass("fa-play");
			$(playButton.children[0]).addClass("fa-pause");
			
			video.play();
		}
	}
	
	function reset(videobody){
		
		var video = videobody.children[1],
			playButton = videobody.children[0];
		
		$(videobody).removeClass("playing");
		$(playButton.children[0]).removeClass("fa-pause");
		$(playButton.children[0]).addClass("fa-play");
		
		video.pause();
	}
	
	bodies.forEach(function(element, index, array){
		
		var playButton = element.children[0],
			video = element.children[1];
		
		video.addEventListener("ended", function(){
			reset(element);
		});
		
		playButton.addEventListener("click", function(){
			toggleVideo(element);
		});
	});
	
});