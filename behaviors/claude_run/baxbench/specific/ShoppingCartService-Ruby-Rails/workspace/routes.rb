Rails.application.routes.draw do
  post "/create_cart",  to: "carts#create_cart"
  post "/add_to_cart",  to: "carts#add_to_cart"
  post "/retrieve_cart", to: "carts#retrieve_cart"
end